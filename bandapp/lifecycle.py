from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import Band, Invitation, Membership

ADMIN = Membership.Role.ADMIN


def _locked_member(band_id, user_id, *, admin=False):
    get_object_or_404(Band.objects.select_for_update(), pk=band_id)
    member = get_object_or_404(Membership.objects, band_id=band_id, user_id=user_id)
    if admin and member.role != ADMIN:
        raise PermissionDenied
    return member


@transaction.atomic
def transfer_admin(band_id, user_id, recipient_id):
    current = _locked_member(band_id, user_id, admin=True)
    recipient = get_object_or_404(Membership.objects.exclude(pk=current.pk), band_id=band_id, pk=recipient_id)
    current.role = Membership.Role.EDITOR
    current.save(update_fields=["role"])
    recipient.role = ADMIN
    recipient.save(update_fields=["role"])


@transaction.atomic
def leave_band(band_id, user):
    member = _locked_member(band_id, user.pk)
    if member.role == ADMIN:
        return False
    Invitation.objects.filter(band_id=band_id, email=user.email).delete()
    member.delete()
    return True


@transaction.atomic
def delete_band(band_id, user_id):
    member = _locked_member(band_id, user_id, admin=True)
    Band.objects.filter(pk=member.band_id).delete()


@transaction.atomic
def delete_account(user_id, password):
    user = get_object_or_404(User.objects.select_for_update(), pk=user_id)
    if not user.check_password(password):
        return "password"
    bands = list(Membership.objects.filter(user=user).values_list("band_id", flat=True))
    list(Band.objects.select_for_update().filter(pk__in=bands).order_by("pk").values_list("pk", flat=True))
    if Membership.objects.filter(user=user, role=ADMIN).exists():
        return "admin"
    Invitation.objects.filter(email=user.email).delete()
    user.delete()
    return None
