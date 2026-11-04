import hashlib
import logging
import secrets
from datetime import timedelta
from functools import wraps
from smtplib import SMTPException

import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Count, Max
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import resolve, reverse, Resolver404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from auswahl import auswahl_gewichte

from .forms import BandForm, DayForm, InviteForm, SignupForm, SongForm
from .models import Band, Invitation, Membership, Plan, Played, Song

logger = logging.getLogger(__name__)
ADMIN = Membership.Role.ADMIN
EDITOR = Membership.Role.EDITOR


def _mail(subject, body, email):
    try:
        send_mail(subject, body, None, [email])
        return True
    except (OSError, SMTPException):
        logger.warning("Songpicker mail delivery failed")
        return False


def _url(name, **kwargs):
    return settings.PUBLIC_URL + reverse(name, kwargs=kwargs)


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("home")
    next_path = request.GET.get("next", "")
    try:
        match = resolve(next_path)
    except Resolver404:
        pass
    else:
        if match.url_name == "accept_invite":
            request.session["pending_invitation"] = reverse("accept_invite", kwargs=match.kwargs)
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            form.add_error("email", "Für diese Adresse gibt es bereits ein Konto.")
        else:
            if _activation(user):
                messages.success(request, "Prüfe dein Postfach und bestätige deine E-Mail-Adresse.")
            else:
                messages.error(request, "E-Mail konnte gerade nicht gesendet werden. Fordere einen neuen Link an.")
            return redirect("login")
    return render(request, "form.html", {"title": "Konto anlegen", "form": form})


def _activation(user):
    link = _url("activate", uid=user.pk, token=default_token_generator.make_token(user))
    return _mail("Songpicker-Konto bestätigen", f"Bestätige deine E-Mail-Adresse im Songpicker:\n\n{link}", user.email)


@require_http_methods(["GET", "POST"])
def resend(request):
    if request.method == "POST":
        user = User.objects.filter(username=request.POST.get("email", "").strip().lower(), is_active=False).first()
        if user:
            _activation(user)
        messages.info(request, "Wenn ein unbestätigtes Konto zu dieser Adresse existiert, erhältst du einen neuen Link.")
        return redirect("login")
    return render(request, "resend.html")


@require_http_methods(["GET", "POST"])
def activate(request, uid, token):
    user = get_object_or_404(User, pk=uid, is_active=False)
    if not default_token_generator.check_token(user, token):
        raise Http404
    if request.method == "POST":
        if not user.check_password(request.POST.get("password", "")):
            messages.error(request, "Das Passwort stimmt nicht.")
        elif User.objects.filter(pk=uid, is_active=False, password=user.password).update(is_active=True):
            user.is_active = True
            login(request, user)
            messages.success(request, "Dein Konto ist bestätigt.")
            return redirect(request.session.pop("pending_invitation", None) or "home")
    return render(request, "confirm.html", {"title": "E-Mail bestätigen", "action": "Konto bestätigen"})


def band_access(*roles):
    def decorate(view):
        @never_cache
        @login_required
        @wraps(view)
        def checked(request, band_id, **kwargs):
            membership = get_object_or_404(
                Membership.objects.select_related("band"), band_id=band_id, user=request.user
            )
            if roles and membership.role not in roles:
                raise PermissionDenied
            return view(request, membership, **kwargs)
        return checked
    return decorate


@never_cache
@login_required
def home(request):
    memberships = Membership.objects.filter(user=request.user).select_related("band").order_by("band__name")
    return render(request, "home.html", {"memberships": memberships})


def _save_band(form):
    band = form.save(commit=False)
    if form.cleaned_data["upload"] is not None:
        band.logo = form.cleaned_data["upload"]
    elif form.cleaned_data["remove"]:
        band.logo = None
    band.save()
    return band


@login_required
@require_http_methods(["GET", "POST"])
def create_band(request):
    form = BandForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            band = _save_band(form)
            Membership.objects.create(band=band, user=request.user, role=ADMIN)
        return redirect("band", band_id=band.pk)
    return render(request, "form.html", {"title": "Band anlegen", "form": form})


@band_access()
def band_page(request, membership):
    band = membership.band
    songs = Song.objects.filter(band=band, archived=False).annotate(times=Count("played"), last=Max("played__day"))
    plan = Plan.objects.filter(band=band).prefetch_related("songs").first()
    history = Played.objects.filter(song__band=band).select_related("song").order_by("-day", "song__title")[:100]
    draft = request.session.get(f"draft_{band.pk}", [])
    draft_songs = songs.filter(pk__in=draft)
    return render(request, "band.html", {
        "membership": membership, "band": band, "songs": songs, "plan": plan, "history": history,
        "can_edit": membership.role in (ADMIN, EDITOR), "draft": draft_songs,
        "today": timezone.localdate().isoformat(), "draft_day": request.session.get(f"day_{band.pk}"), "plan_songs": plan.songs.filter(archived=False) if plan else [],
    })


@band_access()
def logo(request, membership):
    if not membership.band.logo:
        raise Http404
    return HttpResponse(bytes(membership.band.logo), content_type="image/png",
                        headers={"Cache-Control": "private, no-store"})


@band_access(ADMIN)
@require_http_methods(["GET", "POST"])
def band_settings(request, membership):
    band = membership.band
    form = BandForm(request.POST or None, request.FILES or None, instance=band)
    if request.method == "POST" and form.is_valid():
        _save_band(form)
        messages.success(request, "Bandprofil gespeichert.")
        return redirect("band_settings", band_id=band.pk)
    return render(request, "settings.html", {
        "band": band, "form": form, "invite_form": InviteForm(),
        "members": Membership.objects.filter(band=band).select_related("user").order_by("user__email"),
        "invitations": Invitation.objects.filter(band=band, accepted__isnull=True, expires__gt=timezone.now()),
    })


@band_access(ADMIN)
@require_POST
def invite(request, membership):
    band = membership.band
    form = InviteForm(request.POST)
    if form.is_valid():
        email = form.cleaned_data["email"].lower()
        if Membership.objects.filter(band=band, user__email=email).exists():
            messages.info(request, "Dieses Konto ist bereits in der Band.")
        else:
            token = secrets.token_urlsafe(32)
            invitation = Invitation.objects.create(
                band=band, email=email, role=form.cleaned_data["role"], digest=_digest(token),
                expires=timezone.now() + timedelta(days=7),
            )
            link = _url("accept_invite", token=token)
            if _mail("Deine Einladung zum Songpicker", f"Du wurdest zu {band.name} eingeladen.\n\n{link}", email):
                messages.success(request, "Einladung gesendet. Der Link gilt sieben Tage.")
            else:
                invitation.delete()
                messages.error(request, "Einladung konnte nicht gesendet werden. Versuche es erneut.")
    else:
        messages.error(request, "Bitte gib eine gültige E-Mail-Adresse und Rolle an.")
    return redirect("band_settings", band_id=band.pk)


def _digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def accept_invite(request, token):
    queryset = Invitation.objects.filter(
        digest=_digest(token), email=request.user.email.lower(), expires__gt=timezone.now(),
        accepted__isnull=True,
    )
    if request.method == "POST":
        with transaction.atomic():
            invitation = get_object_or_404(queryset.select_for_update())
            Membership.objects.get_or_create(band=invitation.band, user=request.user,
                                             defaults={"role": invitation.role})
            invitation.accepted = timezone.now()
            invitation.save(update_fields=["accepted"])
        return redirect("band", band_id=invitation.band_id)
    invitation = get_object_or_404(queryset)
    return render(request, "confirm.html", {"title": "Bandeinladung", "detail": invitation.band.name,
                                            "action": "Einladung annehmen"})


@band_access(ADMIN)
@require_POST
def revoke_invite(request, membership, invitation_id):
    get_object_or_404(Invitation, pk=invitation_id, band=membership.band, accepted__isnull=True).delete()
    return redirect("band_settings", band_id=membership.band_id)


@band_access(ADMIN)
@require_POST
def change_member(request, membership, member_id):
    member = get_object_or_404(Membership, pk=member_id, band=membership.band)
    if member.role == ADMIN:
        raise PermissionDenied
    role = request.POST.get("role")
    if role == "remove":
        member.delete()
    elif role == "change" and request.POST.get("new_role") in (EDITOR, Membership.Role.MEMBER):
        member.role = request.POST["new_role"]
        member.save(update_fields=["role"])
    else:
        raise PermissionDenied
    return redirect("band_settings", band_id=membership.band_id)


@band_access(ADMIN, EDITOR)
@require_http_methods(["GET", "POST"])
def edit_song(request, membership, song_id=None):
    band = membership.band
    song = get_object_or_404(Song, pk=song_id, band=band, archived=False) if song_id else Song(band=band)
    form = SongForm(request.POST or None, instance=song)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            form.add_error("title", "Ein Song mit diesem Titel existiert bereits in dieser Band.")
        else:
            messages.success(request, "Song gespeichert.")
            return redirect("band", band_id=band.pk)
    return render(request, "form.html", {"title": "Song bearbeiten" if song_id else "Song hinzufügen",
                                          "form": form, "band": band})


@band_access(ADMIN, EDITOR)
@require_POST
def archive_song(request, membership, song_id):
    song = get_object_or_404(Song, pk=song_id, band=membership.band, archived=False)
    song.archived = True
    song.save(update_fields=["archived"])
    messages.success(request, "Song archiviert. Frühere Proben bleiben in der Historie.")
    return redirect("band", band_id=membership.band_id)


@band_access(ADMIN, EDITOR)
@require_POST
def suggest(request, membership):
    form = DayForm(request.POST)
    try:
        count = int(request.POST.get("count", 5))
    except ValueError:
        count = 0
    if not form.is_valid() or not 1 <= count <= 30:
        messages.error(request, "Bitte ein gültiges Datum und 1 bis 30 Songs angeben.")
    else:
        candidates = list(Song.objects.filter(band=membership.band, archived=False, status="set")
                          .annotate(last=Max("played__day")))
        if candidates:
            data = pd.DataFrame([{"id": s.pk, "Zuletzt_gespielt": s.last,
                                  "Reifegrad": s.grade, "Must_Play": s.must_play} for s in candidates])
            weights = auswahl_gewichte(data, form.cleaned_data["day"])
            request.session[f"draft_{membership.band_id}"] = data.sample(
                n=min(count, len(data)), weights=weights
            )["id"].tolist()
            request.session[f"day_{membership.band_id}"] = form.cleaned_data["day"].isoformat()
        else:
            messages.info(request, "Füge mindestens einen Song mit dem Status „Im Set“ hinzu.")
    return redirect("band", band_id=membership.band_id)


def _selected(request, band):
    ids = set(request.POST.getlist("songs"))
    if any(not item.isascii() or not item.isdigit() or len(item) > 18 for item in ids):
        raise Http404
    songs = list(Song.objects.filter(pk__in=ids, band=band, archived=False))
    if len(songs) != len(ids):
        raise Http404
    return songs


@band_access(ADMIN, EDITOR)
@require_POST
def save_plan(request, membership):
    band = membership.band
    form = DayForm(request.POST)
    songs = _selected(request, band)
    if not form.is_valid() or not songs:
        messages.error(request, "Wähle ein gültiges Datum und mindestens einen Song aus.")
    else:
        with transaction.atomic():
            Band.objects.select_for_update().get(pk=band.pk)
            plan, _ = Plan.objects.update_or_create(band=band, defaults={"day": form.cleaned_data["day"]})
            plan.songs.set(songs)
        request.session.pop(f"draft_{band.pk}", None)
        request.session.pop(f"day_{band.pk}", None)
        messages.success(request, "Probe geplant.")
    return redirect("band", band_id=band.pk)


@band_access(ADMIN, EDITOR)
@require_POST
def record(request, membership):
    band = membership.band
    form = DayForm(request.POST)
    songs = _selected(request, band)
    if not form.is_valid() or not songs:
        messages.error(request, "Wähle ein gültiges Datum und die tatsächlich gespielten Songs aus.")
    else:
        with transaction.atomic():
            new = sum(Played.objects.get_or_create(song=song, day=form.cleaned_data["day"])[1]
                      for song in sorted(songs, key=lambda song: song.pk))
        messages.success(request, f"Neu in der Historie erfasst: {new} von {len(songs)} Songs.")
    return redirect("band", band_id=band.pk)
