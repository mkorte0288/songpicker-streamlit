import re
from datetime import date, timedelta
from io import BytesIO
from urllib.parse import urlsplit

from PIL import Image
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Band, Membership, Plan, Played, Song


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccountAndBandTests(TestCase):
    password = "Band-Probe-87-gestimmt"

    def link(self):
        return urlsplit(re.search(r"https?://\S+", mail.outbox[-1].body).group()).path

    def account(self, client, email, next_path=""):
        response = client.post(reverse("signup") + (f"?next={next_path}" if next_path else ""), {
            "email": email, "first_name": email.split("@")[0],
            "password1": self.password, "password2": self.password,
        })
        self.assertRedirects(response, reverse("login"))
        confirmation = self.link()
        self.assertEqual(client.get(confirmation).status_code, 200)
        self.assertFalse(User.objects.get(email=email).is_active)
        self.assertEqual(client.post(confirmation, {"password": "wrong"}).status_code, 200)
        self.assertEqual(client.post(confirmation, {"password": self.password}).status_code, 302)
        self.assertTrue(User.objects.get(email=email).is_active)

    def test_account_invitation_role_and_logo_isolation(self):
        self.account(self.client, "owner@example.com")
        self.client.post(reverse("create_band"), {"name": "Band A"})
        band = Band.objects.get(name="Band A")
        band_page = reverse("band", args=[band.pk])
        settings = reverse("band_settings", args=[band.pk])
        logo = reverse("logo", args=[band.pk])
        out = BytesIO()
        Image.new("RGB", (32, 32), "blue").save(out, "PNG")
        response = self.client.post(settings, {
            "name": "Band A", "upload": SimpleUploadedFile("logo.png", out.getvalue(), "image/png"),
        })
        self.assertRedirects(response, settings)
        self.assertEqual(self.client.get(logo)["Content-Type"], "image/png")

        self.client.post(reverse("invite", args=[band.pk]), {"email": "member@example.com", "role": "member"})
        invitation = self.link()
        member = Client()
        self.assertEqual(member.get(invitation).status_code, 302)
        self.account(member, "member@example.com", invitation)
        self.assertEqual(member.get(invitation).status_code, 200)
        self.assertRedirects(member.post(invitation), band_page)
        self.assertEqual(member.post(invitation).status_code, 404)
        self.assertEqual(member.get(logo).status_code, 200)
        self.assertEqual(member.get(settings).status_code, 403)
        self.assertEqual(member.post(reverse("record", args=[band.pk]), {}).status_code, 403)

        outsider = Client()
        self.account(outsider, "other@example.com")
        self.assertEqual(outsider.get(band_page).status_code, 404)
        self.assertEqual(outsider.get(logo).status_code, 404)
        self.assertEqual(outsider.post(invitation).status_code, 404)

        member_id = Membership.objects.get(band=band, user__email="member@example.com").pk
        self.client.post(reverse("change_member", args=[band.pk, member_id]), {"role": "remove", "confirm": "remove"})
        self.assertEqual(member.get(band_page).status_code, 404)

    def test_reset_and_password_login(self):
        self.account(self.client, "member@example.com")
        self.client.post(reverse("logout"))
        self.assertRedirects(
            self.client.post(reverse("password_reset"), {"email": "member@example.com"}),
            reverse("password_reset_done"),
        )
        link = self.link()
        form_url = self.client.get(link)["Location"]
        new_password = "Saiten-91-Abendprobe"
        self.assertRedirects(
            self.client.post(form_url, {"new_password1": new_password, "new_password2": new_password}),
            reverse("password_reset_complete"),
        )
        self.assertRedirects(self.client.post(reverse("login"), {
            "username": "Member@example.com", "password": new_password,
        }), reverse("home"))

    def test_planning_and_rehearsal_are_scoped_and_idempotent(self):
        self.account(self.client, "owner@example.com")
        self.client.post(reverse("create_band"), {"name": "Band A"})
        band = Band.objects.get(name="Band A")
        self.client.post(reverse("new_song", args=[band.pk]), {
            "title": "Walk", "status": "set", "duration": "4:40", "grade": 7,
        })
        song = Song.objects.get()
        self.assertEqual(song.duration, 280)
        edit_song = reverse("edit_song", args=[band.pk, song.pk])
        self.assertContains(self.client.get(edit_song), 'value="4:40"')
        invalid = self.client.post(edit_song, {"title": "Walk", "status": "set", "duration": "4:60"})
        self.assertContains(invalid, "Gib die Spielzeit als Minuten:Sekunden ein")
        song.refresh_from_db()
        self.assertEqual(song.duration, 280)
        day = (timezone.localdate() + timedelta(days=1)).isoformat()
        suggest = self.client.post(reverse("suggest", args=[band.pk]), {"day": day, "count": 5}, follow=True)
        self.assertContains(suggest, "Vorschlag für")
        self.assertContains(suggest, "Walk")
        plan = self.client.post(reverse("save_plan", args=[band.pk]), {"day": day, "songs": [song.pk]}, follow=True)
        self.assertContains(plan, "Probe geplant.")
        record_page = self.client.get(reverse("band", args=[band.pk]) + f"?tab=erfassen&day={day}")
        self.assertContains(record_page, f'value="{song.pk}" checked')
        record = reverse("record", args=[band.pk])
        for _ in range(2):
            self.assertEqual(self.client.post(record, {"day": day, "songs": [song.pk]}).status_code, 302)
        self.assertEqual(Played.objects.count(), 1)
        self.assertTrue(Plan.objects.get(band=band, day=day).completed)
        self.assertContains(self.client.get(reverse("band", args=[band.pk])), "Es ist keine kommende Probe geplant.")
        rate = self.client.post(reverse("rate_rehearsal", args=[band.pk]), {
            "day": day, f"grade_{song.pk}": "4",
        }, follow=True)
        self.assertContains(rate, "Reifegrade gespeichert.")
        song.refresh_from_db()
        self.assertEqual(song.grade, 4)
        foreign = Song.objects.create(band=Band.objects.create(name="Band B"), title="Fremd")
        self.assertEqual(self.client.post(record, {"day": day, "songs": [foreign.pk]}).status_code, 404)
        self.assertEqual(Played.objects.count(), 1)

    def test_separate_future_plans_import_and_restore(self):
        self.account(self.client, "owner@example.com")
        self.client.post(reverse("create_band"), {"name": "Band A"})
        band = Band.objects.get(name="Band A")
        imported = self.client.post(reverse("import_songs", args=[band.pk]), {
            "titles": "Everlong\nWalk\nEverlong\n",
        }, follow=True)
        self.assertContains(imported, "2 Songs hinzugefügt")
        self.assertEqual(Song.objects.filter(band=band).count(), 2)
        first = Song.objects.get(band=band, title="Everlong")
        day1 = (timezone.localdate() + timedelta(days=1)).isoformat()
        day2 = (timezone.localdate() + timedelta(days=2)).isoformat()
        for day in (day1, day2):
            self.client.post(reverse("save_plan", args=[band.pk]), {"day": day, "songs": [first.pk]})
        self.assertEqual(Plan.objects.filter(band=band).count(), 2)
        first_page = self.client.get(reverse("band", args=[band.pk]))
        self.assertContains(first_page, date.fromisoformat(day1).strftime("%d.%m.%Y"))
        self.client.post(reverse("record", args=[band.pk]), {"day": day1, "songs": [first.pk]})
        next_page = self.client.get(reverse("band", args=[band.pk]))
        self.assertContains(next_page, date.fromisoformat(day2).strftime("%d.%m.%Y"))
        self.assertNotContains(next_page, date.fromisoformat(day1).strftime("%d.%m.%Y"))
        self.client.post(reverse("archive_song", args=[band.pk, first.pk]))
        self.assertTrue(Song.objects.get(pk=first.pk).archived)
        self.client.post(reverse("restore_song", args=[band.pk, first.pk]))
        self.assertFalse(Song.objects.get(pk=first.pk).archived)

    def test_old_csv_import_preserves_counts_and_rejects_second_import(self):
        self.account(self.client, "owner@example.com")
        self.client.post(reverse("create_band"), {"name": "Band A"})
        band = Band.objects.get(name="Band A")
        songs = (
            "Songtitel;Interpret;Status;Spielzeit;Reifegrad;Anzahl_gespielt;Must_Play;Favorit;Tags;Kommentar;Notiz\n"
            "Walk;Foo Fighters;im Set;4:40;7;4;True;False;Laut;Gut;Probe\n"
            "Big Me;Foo Fighters;nicht im Repertoire;;0;0;False;True;;;\n"
        )
        history = "Songtitel;Gespielt_am\nwalk;2026-01-05\nWalk;2026-01-05\n"

        def upload():
            return {
                "songliste": SimpleUploadedFile("songliste.csv", songs.encode()),
                "spielhistorie": SimpleUploadedFile("spielhistorie.csv", history.encode()),
                "confirm": "import",
            }

        url = reverse("import_legacy", args=[band.pk])
        response = self.client.post(url, upload(), follow=True)
        self.assertContains(response, "Songs übernommen: 2. Historieneinträge: 1.")
        self.assertEqual(Played.objects.count(), 1)
        walk = Song.objects.get(band=band, title="Walk")
        self.assertEqual(walk.legacy_play_count, 3)
        self.assertEqual(walk.duration, 280)
        self.assertTrue(walk.must_play)
        self.assertEqual(Song.objects.get(band=band, title="Big Me").status, "out")
        self.assertContains(self.client.get(reverse("band", args=[band.pk]) + "?tab=songs"), "4× laut Zähler")
        self.assertContains(self.client.post(url, upload(), follow=True), "nur für eine leere Band")
        self.assertEqual(Song.objects.filter(band=band).count(), 2)

    def test_admin_transfer_and_deletion_keep_band_usable(self):
        self.account(self.client, "owner@example.com")
        self.client.post(reverse("create_band"), {"name": "Band A"})
        band = Band.objects.get(name="Band A")
        settings = reverse("band_settings", args=[band.pk])
        new_admin = Client()
        self.account(new_admin, "new@example.com")
        successor = Membership.objects.create(
            band=band, user=User.objects.get(email="new@example.com"), role=Membership.Role.MEMBER
        )
        outsider = Membership.objects.create(
            band=Band.objects.create(name="Band B"), user=successor.user, role=Membership.Role.ADMIN
        )
        delete = {"password": self.password, "confirm": "yes"}
        self.client.post(reverse("delete_account"), delete)
        self.assertTrue(User.objects.filter(email="owner@example.com").exists())
        self.client.post(reverse("leave_band", args=[band.pk]))
        self.assertEqual(Membership.objects.filter(band=band).count(), 2)
        target = reverse("transfer_admin", args=[band.pk, successor.pk])
        self.assertEqual(self.client.post(
            reverse("transfer_admin", args=[band.pk, outsider.pk]), delete
        ).status_code, 404)
        self.client.post(target, {"password": "wrong"})
        successor.refresh_from_db()
        self.assertEqual(successor.role, Membership.Role.MEMBER)
        self.assertEqual(self.client.post(target, delete).status_code, 302)
        self.assertEqual(self.client.get(settings).status_code, 403)
        self.assertEqual(new_admin.get(settings).status_code, 200)
        self.assertRedirects(self.client.post(reverse("leave_band", args=[band.pk])), reverse("home"))
        self.assertRedirects(self.client.post(reverse("delete_account"), delete), reverse("login"))
        self.assertFalse(User.objects.filter(email="owner@example.com").exists())
        self.assertTrue(Band.objects.filter(pk=band.pk).exists())
        self.assertRedirects(new_admin.post(reverse("delete_band", args=[band.pk]), delete), reverse("home"))
        self.assertFalse(Band.objects.filter(pk=band.pk).exists())
        self.assertTrue(Band.objects.filter(name="Band B").exists())

    @override_settings(PUBLIC_SIGNUP=False, PREFLIGHT_SIGNUP_EMAILS={"operator@example.com"})
    def test_closed_registration_accepts_only_preflight_addresses(self):
        self.client.post(reverse("signup"), {
            "email": "external@example.com", "password1": self.password, "password2": self.password,
        })
        self.assertFalse(User.objects.filter(email="external@example.com").exists())
        self.account(self.client, "operator@example.com")

    @override_settings(TRUSTED_PROXY_HOPS=2)
    def test_rate_limit_ignores_spoofed_prefix_and_separates_clients(self):
        url = reverse("login")
        shared = {"REMOTE_ADDR": "10.0.0.3"}
        for _ in range(25):
            response = self.client.post(url, {}, **shared, HTTP_X_FORWARDED_FOR="192.0.2.5, 10.0.0.2")
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post(
            url, {}, **shared, HTTP_X_FORWARDED_FOR="198.51.100.1, 192.0.2.5, 10.0.0.2"
        ).status_code, 429)
        self.assertEqual(self.client.post(
            url, {}, **shared, HTTP_X_FORWARDED_FOR="192.0.2.6, 10.0.0.2"
        ).status_code, 200)

    @override_settings(TRUSTED_PROXY_HOPS=0)
    def test_rate_limit_ignores_forwarding_on_direct_connections(self):
        from .limits import client_identity

        self.assertEqual(client_identity({
            "REMOTE_ADDR": "192.0.2.5", "HTTP_X_FORWARDED_FOR": "198.51.100.1",
        }), "192.0.2.5")

    @override_settings(EMAIL_BACKEND="bandapp.mail.BrevoEmailBackend", BREVO_API_KEY="local-test-key")
    def test_transactional_mail_uses_https_and_counts_accepted_messages(self):
        import json
        from unittest.mock import patch

        with patch("bandapp.mail.urlopen") as send:
            send.return_value.__enter__.return_value.status = 201
            self.assertEqual(mail.send_mail(
                "Betreff", "Nachricht", "Songpicker <sender@example.com>", ["member@example.com"]
            ), 1)
            request = send.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.brevo.com/v3/smtp/email")
            self.assertEqual(json.loads(request.data), {
                "sender": {"name": "Songpicker", "email": "sender@example.com"},
                "to": [{"email": "member@example.com"}],
                "subject": "Betreff", "textContent": "Nachricht",
            })
            send.return_value.__enter__.return_value.status = 202
            with self.assertRaises(OSError):
                mail.send_mail("Test", "Text", "sender@example.com", ["member@example.com"])
