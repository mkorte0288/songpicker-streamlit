"""Schreibt geänderte CSV-Dateien zurück ins GitHub-Repository.

Warum das nötig ist: Auf Streamlit Community Cloud ist das Dateisystem
flüchtig. Eine Datei, die die App speichert, ist beim nächsten Neustart
weg. Wer im Browser arbeiten will, braucht deshalb einen Speicherort
ausserhalb der Instanz. Das Repository ist der naheliegende — es ist
ohnehin schon da, versioniert jede Änderung und braucht keine Datenbank.

Konfiguration über Streamlit-Secrets (Menü „Settings" → „Secrets"):

    github_token    = "github_pat_..."
    edit_password   = "..."
    github_repo     = "mkorte0288/songpicker-streamlit"
    github_branch   = "main"
"""

import base64
import hmac

import requests
import streamlit as st

API = "https://api.github.com"
TIMEOUT = 20


def _conf(schluessel, standard=None):
    try:
        return st.secrets.get(schluessel, standard)
    except Exception:
        return standard


def verfuegbar():
    """True, wenn Token und Repository hinterlegt sind."""
    # Preview-Schutz: niemals in main oder die echte Songpicker-Datenbasis schreiben.
    return bool(
        _conf("github_token")
        and _conf("github_repo") == "mkorte0288/songpicker-streamlit"
        and _conf("github_branch") == "preview/songpicker-validation-20261104"
    )


def passwort_gesetzt():
    return bool(_conf("edit_password"))


def pruefe_passwort(eingabe):
    soll = _conf("edit_password")
    return isinstance(soll, str) and isinstance(eingabe, str) and hmac.compare_digest(eingabe, soll)


def _kopf():
    return {
        "Authorization": f"Bearer {_conf('github_token')}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _url(pfad):
    return f"{API}/repos/{_conf('github_repo')}/contents/{pfad}"


def hole_sha(pfad):
    """Aktuelle Blob-SHA einer Datei; None, wenn sie noch nicht existiert."""
    try:
        r = requests.get(
            _url(pfad),
            headers=_kopf(),
            params={"ref": _conf("github_branch", "main")},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return r.json().get("sha")
        return None
    except requests.RequestException:
        return None


def speichere(pfad, inhalt, nachricht):
    """Committet den Inhalt. Gibt (True, Meldung) oder (False, Fehler) zurueck.

    Die SHA wird unmittelbar vor dem Schreiben geholt. Aendert jemand die
    Datei zwischendurch, lehnt GitHub den Commit mit 409 ab — dann geht
    nichts verloren, es schlaegt nur fehl.
    """
    if not verfuegbar():
        return False, "Kein GitHub-Token hinterlegt."

    daten = {
        "message": nachricht,
        "content": base64.b64encode(inhalt.encode("utf-8")).decode("ascii"),
        "branch": _conf("github_branch", "main"),
    }
    sha = hole_sha(pfad)
    if sha:
        daten["sha"] = sha

    try:
        r = requests.put(_url(pfad), headers=_kopf(), json=daten, timeout=TIMEOUT)
    except requests.RequestException as e:
        return False, f"Netzwerkfehler: {e}"

    if r.status_code in (200, 201):
        return True, "Im Repository gespeichert."
    if r.status_code == 409:
        return False, "Die Datei wurde zwischenzeitlich geaendert. Seite neu laden und erneut speichern."
    if r.status_code in (401, 403):
        return False, "Token fehlt, ist abgelaufen oder hat keine Schreibrechte auf Contents."
    return False, f"GitHub antwortete mit {r.status_code}: {r.text[:200]}"
