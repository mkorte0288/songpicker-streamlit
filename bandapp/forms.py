from io import BytesIO

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Band, Membership, Song


class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(label="E-Mail", max_length=150)

    def clean(self):
        if "username" in self.cleaned_data:
            self.cleaned_data["username"] = self.cleaned_data["username"].lower()
        return super().clean()


class SignupForm(UserCreationForm):
    email = forms.EmailField(label="E-Mail", max_length=150)
    first_name = forms.CharField(label="Dein Name", max_length=150)

    class Meta:
        model = User
        fields = ("email", "first_name")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Für diese Adresse gibt es bereits ein Konto.")
        return email

    def save(self):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = user.email
        user.is_active = False
        user.save()
        return user


class BandForm(forms.ModelForm):
    upload = forms.FileField(label="Logo (PNG oder JPEG, bis 2 MB)", required=False)
    remove = forms.BooleanField(label="Logo entfernen", required=False)

    class Meta:
        model = Band
        fields = ("name",)
        labels = {"name": "Bandname"}

    def clean_upload(self):
        upload = self.cleaned_data["upload"]
        if not upload:
            return None
        if upload.size > 2_000_000:
            raise forms.ValidationError("Das Logo darf höchstens 2 MB groß sein.")
        try:
            with Image.open(upload, formats=("PNG", "JPEG")) as image:
                if image.width * image.height > 12_000_000:
                    raise ValueError
                logo = ImageOps.exif_transpose(image).convert("RGBA")
                logo.thumbnail((512, 512))
                out = BytesIO()
                logo.save(out, format="PNG")
                return out.getvalue()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise forms.ValidationError("Bitte ein gültiges PNG- oder JPEG-Bild hochladen.")


class AccountNameForm(forms.ModelForm):
    first_name = forms.CharField(label="Dein Name", max_length=150)

    class Meta:
        model = User
        fields = ("first_name",)


class InviteForm(forms.Form):
    email = forms.EmailField(label="E-Mail")
    role = forms.ChoiceField(label="Rolle", choices=[
        (Membership.Role.MEMBER, Membership.Role.MEMBER.label),
        (Membership.Role.EDITOR, Membership.Role.EDITOR.label),
    ])


class SongForm(forms.ModelForm):
    duration = forms.RegexField(
        regex=r"\A[0-9]{1,8}:[0-5][0-9]\Z",
        label="Spielzeit (Minuten:Sekunden)",
        max_length=11,
        help_text="Zum Beispiel 4:35 für 4 Minuten und 35 Sekunden. Falls unbekannt: 0:00.",
        widget=forms.TextInput(attrs={"placeholder": "4:35"}),
        error_messages={"invalid": "Gib die Spielzeit als Minuten:Sekunden ein, zum Beispiel 4:35."},
    )
    grade = forms.IntegerField(label="Reifegrad (0–10)", required=False, min_value=0, max_value=10)

    class Meta:
        model = Song
        fields = ("title", "artist", "status", "duration", "grade", "must_play", "favorite", "tags", "comment", "note")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        minutes, seconds = divmod(self.initial.get("duration", self.instance.duration), 60)
        self.initial["duration"] = f"{minutes}:{seconds:02d}"

    def clean_duration(self):
        minutes, seconds = map(int, self.cleaned_data["duration"].split(":"))
        duration = minutes * 60 + seconds
        if duration > 24 * 60 * 60:
            raise forms.ValidationError("Die Spielzeit darf höchstens 24 Stunden betragen.")
        return duration


class DayForm(forms.Form):
    day = forms.DateField(label="Probendatum", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
