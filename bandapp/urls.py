from django.contrib.auth.views import LoginView
from django.urls import include, path

from . import views
from .forms import EmailLoginForm

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz/", views.health, name="health"),
    path("konto/loeschen/", views.delete_account, name="delete_account"),
    path("konto/profil/", views.account_profile, name="account_profile"),
    path("konto/login/", LoginView.as_view(authentication_form=EmailLoginForm), name="login"),
    path("konto/", include("django.contrib.auth.urls")),
    path("registrieren/", views.signup, name="signup"),
    path("bestaetigung/", views.resend, name="resend"),
    path("bestaetigen/<int:uid>/<str:token>/", views.activate, name="activate"),
    path("einladung/<str:token>/", views.accept_invite, name="accept_invite"),
    path("bands/neu/", views.create_band, name="create_band"),
    path("bands/<uuid:band_id>/", views.band_page, name="band"),
    path("bands/<uuid:band_id>/verlassen/", views.leave_band, name="leave_band"),
    path("bands/<uuid:band_id>/loeschen/", views.delete_band, name="delete_band"),
    path("bands/<uuid:band_id>/mitglieder/<int:member_id>/admin/", views.transfer_admin, name="transfer_admin"),
    path("bands/<uuid:band_id>/logo/", views.logo, name="logo"),
    path("bands/<uuid:band_id>/einstellungen/", views.band_settings, name="band_settings"),
    path("bands/<uuid:band_id>/einladen/", views.invite, name="invite"),
    path("bands/<uuid:band_id>/einladungen/<int:invitation_id>/widerrufen/", views.revoke_invite, name="revoke_invite"),
    path("bands/<uuid:band_id>/mitglieder/<int:member_id>/", views.change_member, name="change_member"),
    path("bands/<uuid:band_id>/songs/neu/", views.edit_song, name="new_song"),
    path("bands/<uuid:band_id>/songs/<int:song_id>/", views.edit_song, name="edit_song"),
    path("bands/<uuid:band_id>/songs/<int:song_id>/archivieren/", views.archive_song, name="archive_song"),
    path("bands/<uuid:band_id>/songs/<int:song_id>/wiederherstellen/", views.restore_song, name="restore_song"),
    path("bands/<uuid:band_id>/songs/importieren/", views.import_songs, name="import_songs"),
    path("bands/<uuid:band_id>/songs/altbestand/", views.import_legacy, name="import_legacy"),
    path("bands/<uuid:band_id>/vorschlag/", views.suggest, name="suggest"),
    path("bands/<uuid:band_id>/vorschlag/aendern/", views.change_draft, name="change_draft"),
    path("bands/<uuid:band_id>/planung/laden/", views.load_plan, name="load_plan"),
    path("bands/<uuid:band_id>/planen/", views.save_plan, name="save_plan"),
    path("bands/<uuid:band_id>/erfassen/", views.record, name="record"),
    path("bands/<uuid:band_id>/nachbereitung/", views.rate_rehearsal, name="rate_rehearsal"),
]
