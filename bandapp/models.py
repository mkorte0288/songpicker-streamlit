import uuid

from django.conf import settings
from django.db import models


class Band(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    logo = models.BinaryField(null=True, editable=False)


class Membership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        EDITOR = "editor", "Bearbeitung"
        MEMBER = "member", "Mitglied"

    band = models.ForeignKey(Band, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=8, choices=Role.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["band", "user"], name="unique_band_member"),
            models.UniqueConstraint(fields=["band"], condition=models.Q(role="admin"), name="one_band_admin"),
        ]


class Invitation(models.Model):
    band = models.ForeignKey(Band, on_delete=models.CASCADE)
    email = models.EmailField()
    role = models.CharField(max_length=8, choices=Membership.Role.choices)
    digest = models.CharField(max_length=64, unique=True)
    expires = models.DateTimeField()
    accepted = models.DateTimeField(null=True)


class Song(models.Model):
    band = models.ForeignKey(Band, on_delete=models.CASCADE)
    title = models.CharField("Titel", max_length=160)
    artist = models.CharField("Interpret", max_length=160, blank=True)
    status = models.CharField("Status", max_length=20, choices=[
        ("set", "Im Set"), ("work", "In Arbeit"), ("candidate", "Kandidat"),
    ], default="set")
    duration = models.PositiveIntegerField("Spielzeit in Sekunden", default=0)
    grade = models.PositiveSmallIntegerField("Reifegrad (0–10)", null=True, blank=True)
    must_play = models.BooleanField("Must-Play", default=False)
    comment = models.TextField("Kommentar", max_length=1000, blank=True)
    archived = models.BooleanField(default=False)

    @property
    def duration_label(self):
        minutes, seconds = divmod(self.duration, 60)
        return f"{minutes}:{seconds:02d}"

    class Meta:
        ordering = ["title"]
        constraints = [models.UniqueConstraint(fields=["band", "title"], name="unique_band_song_title")]


class Played(models.Model):
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    day = models.DateField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["song", "day"], name="unique_song_day")]


class Plan(models.Model):
    band = models.ForeignKey(Band, on_delete=models.CASCADE)
    day = models.DateField()
    songs = models.ManyToManyField(Song)
    completed = models.BooleanField(default=False)

    class Meta:
        ordering = ["day"]
        constraints = [models.UniqueConstraint(fields=["band", "day"], name="unique_band_plan_day")]


class RequestLimit(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    expires = models.DateTimeField(db_index=True)
    attempts = models.PositiveIntegerField(default=0)
