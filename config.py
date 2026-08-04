"""Zentrale Konfiguration des Songpickers.

Farben und Schriften sind aus der Foo-Fightclub-Website uebernommen
(assets/css/styles.css, Stand v16), damit App und Homepage zusammenpassen.
"""

import os

APP_CONFIG = {
    "title": "Songpicker",
    "files": {
        "songs": "songliste.csv",
        "history": "spielhistorie.csv",
        "naechste_probe": "naechste_probe.csv",
        "logo": "logo_white_foo_fight.png",
        "backup_dir": "backups",
    },
    # Palette der Website
    "theme": {
        "ink": "#101722",        # Hintergrund
        "ink_2": "#182332",      # Karten
        "slate": "#35455d",
        "slate_deep": "#233044",
        "paper": "#e7ded1",      # Text
        "white": "#fff9f1",
        "red": "#d33b2e",        # Akzent
        "red_bright": "#ff6550",
        "muted": "#aab3bf",
        "line": "rgba(231,222,209,.17)",
    },
    # Reifegrad-Skala: rot -> gelb -> gruen, aber in den Websitefarben gedaempft
    "reifegrad": {
        "low": "#d33b2e",
        "mid": "#d9a441",
        "high": "#4f9d69",
    },
}

# --- Bearbeitungsmodus -------------------------------------------------
# Die App laeuft standardmaessig NUR-LESEN. Das ist Absicht: auf Streamlit
# Community Cloud ist das Dateisystem fluechtig, gespeicherte Aenderungen
# waeren beim naechsten Neustart weg.
#
# Ablauf: lokal bearbeiten -> CSVs ins Git-Repo committen -> die
# veroeffentlichte App zeigt der Band den aktuellen Stand.
#
# Lokal einschalten:   SONGPICKER_EDIT=1 streamlit run songpicker_streamlit.py
EDIT_MODE = os.environ.get("SONGPICKER_EDIT", "").strip() in ("1", "true", "yes", "ja")
