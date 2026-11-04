import hashlib
import logging
import secrets
from datetime import timedelta
from functools import wraps
from smtplib import SMTPException
from urllib.parse import urlencode

import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import IntegrityError, connection, transaction
from django.db.models import Count, F, Max
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import resolve, reverse, Resolver404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from auswahl import auswahl_gewichte

from . import legacy_import, lifecycle
from .forms import AccountNameForm, BandForm, DayForm, InviteForm, SignupForm, SongForm
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


def _tab_url(band_id, tab, **query):
    return reverse("band", kwargs={"band_id": band_id}) + "?" + urlencode({"tab": tab, **query})


def _duration(seconds):
    minutes, rest = divmod(seconds, 60)
    return f"{minutes}:{rest:02d}"


@require_http_methods(["GET", "POST"])
def signup(request):
    if not settings.PUBLIC_SIGNUP and not settings.PREFLIGHT_SIGNUP_EMAILS:
        raise Http404
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
    if request.method == "POST" and not settings.PUBLIC_SIGNUP and (
        request.POST.get("email", "").strip().lower() not in settings.PREFLIGHT_SIGNUP_EMAILS
    ):
        messages.info(request, "Die öffentliche Registrierung ist noch geschlossen.")
        return redirect("login")
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


@login_required
@require_http_methods(["GET", "POST"])
def account_profile(request):
    form = AccountNameForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Name gespeichert.")
        return redirect("account_profile")
    return render(request, "form.html", {"title": "Mein Profil", "form": form})


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
            User.objects.select_for_update().get(pk=request.user.pk)
            band = _save_band(form)
            Membership.objects.create(band=band, user=request.user, role=ADMIN)
        return redirect("band", band_id=band.pk)
    return render(request, "form.html", {"title": "Band anlegen", "form": form})


@band_access()
def band_page(request, membership):
    band = membership.band
    tab = request.GET.get("tab", "naechste")
    if tab not in {"naechste", "planen", "erfassen", "nachbereitung", "songs", "historie", "analyse"}:
        raise Http404
    can_edit = membership.role in (ADMIN, EDITOR)
    if tab in {"planen", "erfassen", "nachbereitung"} and not can_edit:
        raise PermissionDenied
    today = timezone.localdate()
    songs = list(Song.objects.filter(band=band, archived=False)
                 .annotate(times=Count("played") + F("legacy_play_count"), last=Max("played__day")))
    song_by_id = {song.pk: song for song in songs}
    next_plan = (Plan.objects.filter(band=band, day__gte=today, completed=False)
                 .prefetch_related("songs").first())
    plans = list(Plan.objects.filter(band=band, day__gte=today, completed=False)
                 .prefetch_related("songs")[:10])
    plan_songs = [song for song in next_plan.songs.all() if not song.archived] if next_plan else []
    draft_ids = request.session.get(f"draft_{band.pk}", [])
    draft_songs = [song_by_id[pk] for pk in draft_ids if pk in song_by_id]
    for song in draft_songs:
        reasons = [f"Reifegrad {song.grade}" if song.grade is not None else "Reifegrad noch offen"]
        reasons.append(f"zuletzt {song.last.strftime('%d.%m.%Y')}" if song.last else "noch nie erfasst")
        if song.must_play:
            reasons.append("Must-Play")
        song.reason = " · ".join(reasons)
    record_day_form = DayForm(request.GET) if request.GET.get("day") else None
    record_day = (record_day_form.cleaned_data["day"] if record_day_form and record_day_form.is_valid()
                  else next_plan.day if next_plan else today)
    record_plan = Plan.objects.filter(band=band, day=record_day).prefetch_related("songs").first()
    record_ids = {song.pk for song in record_plan.songs.all()} if record_plan else set()
    record_songs = [song for song in songs if song.pk in record_ids]
    other_songs = [song for song in songs if song.pk not in record_ids]
    history = list(Played.objects.filter(song__band=band).select_related("song")
                   .order_by("-day", "song__title")[:200])
    review_day_form = DayForm(request.GET) if request.GET.get("day") else None
    review_day = (review_day_form.cleaned_data["day"] if review_day_form and review_day_form.is_valid()
                  else history[0].day if history else None)
    reviewed = list(Played.objects.filter(song__band=band, day=review_day).select_related("song")
                    .order_by("song__title")) if review_day else []
    for item in reviewed:
        item.initial_grade = item.song.grade if item.song.grade is not None else 5
    search = request.GET.get("q", "").strip()[:100]
    status = request.GET.get("status", "")
    listed_songs = [song for song in songs if (not search or search.casefold() in song.title.casefold()
                    or search.casefold() in song.artist.casefold()) and (not status or song.status == status)]
    sort = request.GET.get("sort", "title")
    if sort == "played":
        listed_songs.sort(key=lambda song: (-song.times, song.title.casefold()))
    elif sort == "grade":
        listed_songs.sort(key=lambda song: (song.grade is None, song.grade if song.grade is not None else 11,
                                           song.title.casefold()))
    else:
        sort = "title"
    ungraded = [song for song in songs if song.grade is None]
    rated = [song.grade for song in songs if song.grade is not None]
    grades = [{"value": value, "count": rated.count(value)} for value in range(11)]
    return render(request, "band.html", {
        "membership": membership, "band": band, "tab": tab, "songs": songs, "history": history,
        "can_edit": can_edit, "next_plan": next_plan, "plans": plans, "plan_songs": plan_songs,
        "plan_duration": _duration(sum(song.duration for song in plan_songs)),
        "draft_songs": draft_songs, "draft_duration": _duration(sum(song.duration for song in draft_songs)),
        "addable_songs": [song for song in songs if song not in draft_songs],
        "today": today.isoformat(), "draft_day": request.session.get(f"day_{band.pk}"),
        "record_day": record_day.isoformat(), "record_plan": record_plan,
        "record_songs": record_songs, "other_songs": other_songs,
        "review_day": review_day, "reviewed": reviewed,
        "listed_songs": listed_songs, "search": search, "status_filter": status, "sort": sort,
        "archived_songs": Song.objects.filter(band=band, archived=True),
        "ungraded": ungraded, "rated_average": round(sum(rated) / len(rated), 1) if rated else None,
        "grades": grades, "set_songs": [song for song in songs if song.status == "set"],
        "set_duration": _duration(sum(song.duration for song in songs if song.status == "set")),
        "under_four": len([grade for grade in rated if grade < 4]),
        "rehearsal_count": Played.objects.filter(song__band=band).values("day").distinct().count(),
        "top_songs": sorted(songs, key=lambda song: song.times, reverse=True)[:10],
        "legacy_count": sum(song.legacy_play_count for song in songs),
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
            User.objects.select_for_update().get(pk=request.user.pk)
            candidate = get_object_or_404(queryset)
            get_object_or_404(Band.objects.select_for_update(), pk=candidate.band_id)
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
    with transaction.atomic():
        lifecycle._locked_member(membership.band_id, request.user.pk, admin=True)
        member = get_object_or_404(Membership, pk=member_id, band=membership.band)
        if member.role == ADMIN:
            raise PermissionDenied
        role = request.POST.get("role")
        if role == "remove" and request.POST.get("confirm") == "remove":
            Invitation.objects.filter(band=membership.band, email=member.user.email).delete()
            member.delete()
            messages.success(request, "Zugang entfernt.")
        elif role == "change" and request.POST.get("new_role") in (EDITOR, Membership.Role.MEMBER):
            member.role = request.POST["new_role"]
            member.save(update_fields=["role"])
            messages.success(request, "Rolle gespeichert. Du kannst sie hier jederzeit erneut ändern.")
        else:
            raise PermissionDenied
    return redirect("band_settings", band_id=membership.band_id)


@band_access(ADMIN)
@require_POST
def transfer_admin(request, membership, member_id):
    if not request.user.check_password(request.POST.get("password", "")):
        messages.error(request, "Das Passwort stimmt nicht.")
        return redirect("band_settings", band_id=membership.band_id)
    lifecycle.transfer_admin(membership.band_id, request.user.pk, member_id)
    messages.success(request, "Die Band-Administration wurde übertragen. Du kannst weiter bearbeiten.")
    return redirect("band", band_id=membership.band_id)


@band_access()
@require_POST
def leave_band(request, membership):
    if not lifecycle.leave_band(membership.band_id, request.user):
        messages.error(request, "Übertrage zuerst die Band-Administration oder lösche die Band.")
        return redirect("band", band_id=membership.band_id)
    messages.success(request, "Du hast die Band verlassen.")
    return redirect("home")


@band_access(ADMIN)
@require_http_methods(["GET", "POST"])
def delete_band(request, membership):
    band = membership.band
    if request.method == "POST":
        if request.user.check_password(request.POST.get("password", "")) and request.POST.get("confirm") == "yes":
            lifecycle.delete_band(band.pk, request.user.pk)
            messages.success(request, "Die Band und ihre Daten wurden gelöscht.")
            return redirect("home")
        messages.error(request, "Bestätige die Löschung und gib dein aktuelles Passwort ein.")
    return render(request, "delete.html", {
        "title": "Band löschen", "detail": f"{band.name}, Logo, Songliste und Proben werden dauerhaft gelöscht.",
    })


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def delete_account(request):
    if request.method == "POST" and request.POST.get("confirm") == "yes":
        error = lifecycle.delete_account(request.user.pk, request.POST.get("password", ""))
        if error is None:
            logout(request)
            messages.success(request, "Dein Konto und deine Mitgliedschaften wurden gelöscht.")
            return redirect("login")
        if error == "admin":
            messages.error(request, "Übertrage zuerst die Administration deiner Bands oder lösche diese Bands.")
        else:
            messages.error(request, "Das Passwort stimmt nicht.")
    return render(request, "delete.html", {
        "title": "Konto löschen", "detail": "Dein Konto und deine Mitgliedschaften werden dauerhaft gelöscht.",
    })


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")


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
            return redirect(_tab_url(band.pk, "songs"))
    return render(request, "form.html", {"title": "Song bearbeiten" if song_id else "Song hinzufügen",
                                          "form": form, "band": band})


@band_access(ADMIN, EDITOR)
@require_POST
def archive_song(request, membership, song_id):
    song = get_object_or_404(Song, pk=song_id, band=membership.band, archived=False)
    song.archived = True
    song.save(update_fields=["archived"])
    messages.success(request, "Song archiviert. Frühere Proben bleiben in der Historie.")
    return redirect(_tab_url(membership.band_id, "songs"))


@band_access(ADMIN, EDITOR)
@require_POST
def restore_song(request, membership, song_id):
    song = get_object_or_404(Song, pk=song_id, band=membership.band, archived=True)
    song.archived = False
    song.save(update_fields=["archived"])
    messages.success(request, "Song wiederhergestellt.")
    return redirect(_tab_url(membership.band_id, "songs"))


@band_access(ADMIN, EDITOR)
@require_POST
def suggest(request, membership):
    form = DayForm(request.POST)
    try:
        count = int(request.POST.get("count", 5))
    except ValueError:
        count = 0
    if not form.is_valid() or not 1 <= count <= 30 or form.cleaned_data.get("day", timezone.localdate()) < timezone.localdate():
        messages.error(request, "Bitte ein heutiges oder künftiges Datum und 1 bis 30 Songs angeben.")
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
            messages.success(request, "Vorschlag erstellt. Prüfe die Auswahl und speichere die Probe.")
        else:
            messages.info(request, "Füge mindestens einen Song mit dem Status „Im Set“ hinzu.")
    return redirect(_tab_url(membership.band_id, "planen") + "#vorschlag")


@band_access(ADMIN, EDITOR)
@require_POST
def change_draft(request, membership):
    try:
        song_id = int(request.POST.get("song", ""))
    except ValueError:
        raise Http404
    song = get_object_or_404(Song, pk=song_id, band=membership.band, archived=False)
    key = f"draft_{membership.band_id}"
    draft = list(request.session.get(key, []))
    action = request.POST.get("action")
    if action == "add" and song.pk not in draft and len(draft) >= 30:
        messages.error(request, "Ein Vorschlag kann höchstens 30 Songs enthalten.")
    elif action == "add" and song.pk not in draft:
        draft.append(song.pk)
    elif action == "remove" and song.pk in draft:
        draft.remove(song.pk)
    elif action not in {"add", "remove"}:
        raise Http404
    request.session[key] = draft
    return redirect(_tab_url(membership.band_id, "planen") + "#vorschlag")


@band_access(ADMIN, EDITOR)
@require_POST
def load_plan(request, membership):
    form = DayForm(request.POST)
    if not form.is_valid():
        raise Http404
    plan = get_object_or_404(Plan, band=membership.band, day=form.cleaned_data["day"], completed=False)
    request.session[f"draft_{membership.band_id}"] = list(plan.songs.values_list("pk", flat=True))
    request.session[f"day_{membership.band_id}"] = plan.day.isoformat()
    return redirect(_tab_url(membership.band_id, "planen") + "#vorschlag")


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
    draft = request.session.get(f"draft_{band.pk}", [])
    if request.POST.getlist("songs"):
        songs = _selected(request, band)
    else:
        songs = list(Song.objects.filter(pk__in=draft, band=band, archived=False))
        if len(songs) != len(set(draft)):
            raise Http404
    if (not form.is_valid() or form.cleaned_data.get("day", timezone.localdate()) < timezone.localdate()
            or not songs or len(songs) > 30):
        messages.error(request, "Wähle ein heutiges oder künftiges Datum und 1 bis 30 Songs aus.")
    else:
        with transaction.atomic():
            Band.objects.select_for_update().get(pk=band.pk)
            plan, _ = Plan.objects.update_or_create(
                band=band, day=form.cleaned_data["day"], defaults={"completed": False}
            )
            plan.songs.set(songs)
        request.session.pop(f"draft_{band.pk}", None)
        request.session.pop(f"day_{band.pk}", None)
        messages.success(request, "Probe geplant.")
    return redirect(_tab_url(band.pk, "naechste"))


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
            Plan.objects.filter(band=band, day=form.cleaned_data["day"]).update(completed=True)
        messages.success(request, f"Neu in der Historie erfasst: {new} von {len(songs)} Songs.")
        return redirect(_tab_url(band.pk, "nachbereitung", day=form.cleaned_data["day"].isoformat()))
    return redirect(_tab_url(band.pk, "erfassen"))


@band_access(ADMIN, EDITOR)
@require_POST
def rate_rehearsal(request, membership):
    form = DayForm(request.POST)
    if not form.is_valid():
        raise Http404
    day = form.cleaned_data["day"]
    played = list(Played.objects.filter(song__band=membership.band, day=day).select_related("song"))
    if not played:
        raise Http404
    updates = []
    for item in played:
        try:
            grade = int(request.POST[f"grade_{item.song_id}"])
        except (KeyError, ValueError):
            messages.error(request, "Bitte bewerte alle gespielten Songs von 0 bis 10.")
            return redirect(_tab_url(membership.band_id, "nachbereitung", day=day.isoformat()))
        if not 0 <= grade <= 10:
            raise Http404
        item.song.grade = grade
        updates.append(item.song)
    Song.objects.bulk_update(updates, ["grade"])
    messages.success(request, "Reifegrade gespeichert.")
    return redirect(_tab_url(membership.band_id, "nachbereitung", day=day.isoformat()))


@band_access(ADMIN, EDITOR)
@require_POST
def import_songs(request, membership):
    lines = [line.strip() for line in request.POST.get("titles", "").splitlines() if line.strip()]
    if not lines or len(lines) > 200 or any(len(line) > 160 for line in lines):
        messages.error(request, "Gib 1 bis 200 Titel ein, je einen pro Zeile (höchstens 160 Zeichen).")
        return redirect(_tab_url(membership.band_id, "songs"))
    existing = {title.casefold() for title in Song.objects.filter(band=membership.band).values_list("title", flat=True)}
    unique = []
    for title in lines:
        if title.casefold() not in existing:
            unique.append(Song(band=membership.band, title=title))
            existing.add(title.casefold())
    Song.objects.bulk_create(unique)
    messages.success(request, f"{len(unique)} Songs hinzugefügt; {len(lines) - len(unique)} Duplikate übersprungen.")
    return redirect(_tab_url(membership.band_id, "songs"))


@band_access(ADMIN)
@require_POST
def import_legacy(request, membership):
    if request.POST.get("confirm") != "import":
        raise PermissionDenied
    song_upload = request.FILES.get("songliste")
    history_upload = request.FILES.get("spielhistorie")
    if not song_upload or not history_upload:
        messages.error(request, "Wähle Songliste und Spielhistorie aus.")
        return redirect(_tab_url(membership.band_id, "songs"))
    try:
        prepared, played, duplicates, corrections = legacy_import.parse_legacy(song_upload, history_upload)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect(_tab_url(membership.band_id, "songs"))
    with transaction.atomic():
        Band.objects.select_for_update().get(pk=membership.band_id)
        if Song.objects.filter(band=membership.band).exists():
            messages.error(request, "Die alte Datenübernahme ist nur für eine leere Band möglich.")
            return redirect(_tab_url(membership.band_id, "songs"))
        song_by_title = {}
        for item in prepared:
            song = Song.objects.create(band=membership.band, **item)
            song_by_title[legacy_import._key(song.title)] = song
        Played.objects.bulk_create([
            Played(song=song_by_title[key], day=day) for key, day in played
        ])
    messages.success(request,
        f"Songs übernommen: {len(prepared)}. Historieneinträge: {len(played)}. "
        f"{duplicates} doppelte Historienzeilen ausgelassen; bei {corrections} Songs war "
        "der Historienzähler höher als der alte Gesamtzähler.")
    return redirect(_tab_url(membership.band_id, "songs"))
