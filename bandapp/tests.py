import re
from io import BytesIO
from urllib.parse import urlsplit

from PIL import Image
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Band, Membership, Played, Song


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccountAndBandTests(TestCase):
    password = "Band-Probe-87-gestimmt"

    def link(self):
        return urlsplit(re.search(r"https?://\S+", mail.outbox[-1].body).group()).path

    def account(self, client, email, next_path=""):
        response = client.post(reverse("signup") + (f"?next={next_path}" if next_path else ""), {
            "email": email, "password1": self.password, "password2": self.password,
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
        self.client.post(reverse("change_member", args=[band.pk, member_id]), {"role": "remove"})
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
            "title": "Walk", "status": "set", "duration": 280, "grade": 7,
        })
        song = Song.objects.get()
        day = "2026-11-04"
        suggest = self.client.post(reverse("suggest", args=[band.pk]), {"day": day, "count": 5}, follow=True)
        self.assertContains(suggest, "Für die Probe geplante Songs")
        plan = self.client.post(reverse("save_plan", args=[band.pk]), {"day": day, "songs": [song.pk]}, follow=True)
        self.assertContains(plan, "Probe geplant.")
        record = reverse("record", args=[band.pk])
        for _ in range(2):
            self.assertEqual(self.client.post(record, {"day": day, "songs": [song.pk]}).status_code, 302)
        self.assertEqual(Played.objects.count(), 1)
        foreign = Song.objects.create(band=Band.objects.create(name="Band B"), title="Fremd")
        self.assertEqual(self.client.post(record, {"day": day, "songs": [foreign.pk]}).status_code, 404)
        self.assertEqual(Played.objects.count(), 1)
