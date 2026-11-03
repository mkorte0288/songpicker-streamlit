import os
from io import StringIO

import pandas as pd
import streamlit as st  # war vorher nicht importiert, obwohl st.error() benutzt wurde

from config import APP_CONFIG, EDIT_ENV
import github_speicher
from utils import backup_dateien, parse_datum, spielzeit_in_sekunden

SPALTEN = {
    "Songtitel": "",
    "Interpret": "Foo Fighters",
    "Status": "zu klaeren",       # im Set | in Arbeit | Kandidat | nicht im Repertoire | zu klaeren
    "Spielzeit": "",              # mm:ss
    "Reifegrad": pd.NA,           # darf leer bleiben: „noch nicht bewertet"
    "Anzahl_gespielt": 0,
    "Kommentar": "",
    "Tags": "",
    "Must_Play": False,
    "Favorit": False,
    "Notiz": "",
}


class DataManager:
    """Alle Lese- und Schreibzugriffe auf die CSV-Dateien."""

    @staticmethod
    def lade_songliste():
        pfad = APP_CONFIG["files"]["songs"]
        try:
            if not os.path.exists(pfad):
                df = pd.DataFrame(columns=list(SPALTEN))
                df.to_csv(pfad, sep=";", index=False)
                return df

            df = pd.read_csv(pfad, sep=";", encoding="utf-8-sig")
            df.columns = df.columns.str.strip()
            for spalte, default in SPALTEN.items():
                if spalte not in df.columns:
                    df[spalte] = default

            # Zuletzt_gespielt ist keine Pflichtspalte mehr — der Wert wird in
            # songliste_mit_historie() aus der Spielhistorie abgeleitet. Aeltere
            # Dateien bringen die Spalte aber noch mit.
            if "Zuletzt_gespielt" in df.columns:
                df["Zuletzt_gespielt"] = parse_datum(df["Zuletzt_gespielt"]).fillna(
                    pd.Timestamp("1900-01-01")
                )
            else:
                df["Zuletzt_gespielt"] = pd.Timestamp("1900-01-01")
            # Reifegrad darf leer sein. Ein pauschales fillna(5) hat frueher
            # dazu gefuehrt, dass 19 unbewertete Songs wie bewertete aussahen.
            df["Reifegrad"] = (
                pd.to_numeric(df["Reifegrad"], errors="coerce").clip(0, 10).astype("Int64")
            )
            df["Anzahl_gespielt"] = (
                pd.to_numeric(df["Anzahl_gespielt"], errors="coerce").fillna(0).astype(int)
            )
            for flag in ("Must_Play", "Favorit"):
                df[flag] = (
                    df[flag]
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .isin(["true", "1", "ja", "wahr", "x"])
                )
            for text in ("Kommentar", "Tags", "Notiz", "Interpret", "Status", "Spielzeit"):
                df[text] = df[text].fillna("").astype(str).replace("nan", "")
            return df
        except Exception as e:
            st.error(f"Songliste konnte nicht gelesen werden: {e}")
            return pd.DataFrame(columns=list(SPALTEN))

    @staticmethod
    def songliste_mit_historie():
        """Songliste, bei der das Datum aus der Spielhistorie abgeleitet wird.

        Warum: In der gewachsenen songliste.csv steht das Datum mal als
        05/08/2025 und mal als 08/05/2025 — beides fuer denselben Tag.
        Ausserdem widerspricht die Spalte der Historie. Ein abgeleiteter
        Wert kann gar nicht erst auseinanderlaufen.
        """
        df = DataManager.lade_songliste()
        hist = DataManager.lade_history()
        df["Datum_aus_Historie"] = False
        if "Zuletzt_gespielt" not in df.columns:
            df["Zuletzt_gespielt"] = pd.Timestamp("1900-01-01")
        df["Anzahl_laut_Historie"] = 0
        if df.empty or hist.empty:
            return df

        letzte = hist.groupby("Songtitel")["Gespielt_am"].max()
        anzahl = hist["Songtitel"].value_counts()
        for i, titel in df["Songtitel"].items():
            if titel in letzte.index:
                df.at[i, "Zuletzt_gespielt"] = letzte[titel]
                df.at[i, "Datum_aus_Historie"] = True
            df.at[i, "Anzahl_laut_Historie"] = int(anzahl.get(titel, 0))
        return df

    @staticmethod
    def speichere_songliste(df):
        try:
            df = df.copy()
            for spalte, default in SPALTEN.items():
                if spalte not in df.columns:
                    df[spalte] = default
            df = df[list(SPALTEN)]
            inhalt = StringIO()
            df.to_csv(inhalt, sep=";", index=False)
            pfad = APP_CONFIG["files"]["songs"]
            if os.path.exists(pfad):
                backup_dateien()
            return DataManager._schreibe_mit_sync(pfad, inhalt.getvalue(), "Songliste aktualisiert")
        except Exception as e:
            st.error(f"Songliste konnte nicht gespeichert werden: {e}")
            return False

    @staticmethod
    def lade_history():
        pfad = APP_CONFIG["files"]["history"]
        try:
            if not os.path.exists(pfad):
                return pd.DataFrame(columns=["Songtitel", "Gespielt_am"])
            df = pd.read_csv(pfad, sep=";", encoding="utf-8-sig")
            df.columns = df.columns.str.strip()
            df["Gespielt_am"] = parse_datum(df["Gespielt_am"])
            df = df.dropna(subset=["Gespielt_am"])
            # Ein Song kann an einem Abend nur einmal gespielt worden sein.
            # In der gewachsenen Datei stand "Run" 17-mal fuer denselben
            # Probentag — offenbar wurde beim Eintragen mehrfach angehaengt.
            return df.drop_duplicates(subset=["Songtitel", "Gespielt_am"])
        except Exception as e:
            st.error(f"Spielhistorie konnte nicht gelesen werden: {e}")
            return pd.DataFrame(columns=["Songtitel", "Gespielt_am"])

    @staticmethod
    def _schreibe_mit_sync(pfad, inhalt, nachricht):
        """Lokal speichern und bei GitHub-Fehler den alten Stand wiederherstellen.

        Lokal ohne GitHub ist nur im ausdrücklich aktivierten lokalen Edit-Modus erlaubt.
        Auf der Community Cloud wäre eine rein lokale Erfolgsmeldung irreführend.
        """
        if not github_speicher.verfuegbar() and not EDIT_ENV:
            st.error("Speichern nicht möglich: GitHub-Synchronisierung ist nicht konfiguriert.")
            return False
        existiert = os.path.exists(pfad)
        try:
            vorher = None
            if existiert:
                with open(pfad, encoding="utf-8") as datei:
                    vorher = datei.read()
            tmp = f"{pfad}.tmp"
            with open(tmp, "w", encoding="utf-8", newline="") as datei:
                datei.write(inhalt)
            os.replace(tmp, pfad)
            if github_speicher.verfuegbar():
                ok, meldung = github_speicher.speichere(pfad, inhalt, nachricht)
                if not ok:
                    try:
                        if existiert:
                            with open(tmp, "w", encoding="utf-8", newline="") as datei:
                                datei.write(vorher)
                            os.replace(tmp, pfad)
                        else:
                            os.remove(pfad)
                    except OSError as e:
                        st.error(f"Wiederherstellung der lokalen Datei fehlgeschlagen: {e}")
                    st.error(f"Änderung nicht gespeichert: {meldung}")
                    return False
                st.toast(meldung, icon="✅")
            return True
        except Exception as e:
            st.error(f"Datei konnte nicht gespeichert werden: {e}")
            return False
        finally:
            if os.path.exists(f"{pfad}.tmp"):
                os.remove(f"{pfad}.tmp")

    @staticmethod
    def speichere_history(df):
        try:
            inhalt = StringIO()
            df.to_csv(inhalt, sep=";", index=False)
            return DataManager._schreibe_mit_sync(
                APP_CONFIG["files"]["history"], inhalt.getvalue(), "Spielhistorie aktualisiert"
            )
        except Exception as e:
            st.error(f"Spielhistorie konnte nicht gespeichert werden: {e}")
            return False

    @staticmethod
    def ergaenze_history(songtitel, datum):
        """Nur neue (Song, Probentag)-Kombinationen ergänzen.

        Rückgabe: (erfolg, tatsaechlich_neu_erfasste_songtitel).
        """
        try:
            bestand = DataManager.lade_history()
            tag = pd.Timestamp(datum).normalize()
            vorhanden = set(
                zip(bestand["Songtitel"], bestand["Gespielt_am"].dt.normalize())
            )
            neue_titel = [
                s for s in dict.fromkeys(songtitel) if (s, tag) not in vorhanden
            ]
            if not neue_titel:
                return True, []
            neu = pd.DataFrame({
                "Songtitel": neue_titel,
                "Gespielt_am": [tag] * len(neue_titel),
            })
            zusammen = pd.concat([bestand, neu], ignore_index=True)
            if DataManager.speichere_history(zusammen):
                return True, neue_titel
            return False, []
        except Exception as e:
            st.error(f"Spielhistorie konnte nicht ergaenzt werden: {e}")
            return False, []

    @staticmethod
    def bereinige_history():
        """Entdoppelte Historie speichern: (vorher, nachher, erfolg)."""
        try:
            roh = pd.read_csv(APP_CONFIG["files"]["history"], sep=";", encoding="utf-8-sig")
            vorher = len(roh)
        except Exception:
            vorher = 0
        sauber = DataManager.lade_history()
        ok = DataManager.speichere_history(sauber)
        return vorher, len(sauber), ok

    @staticmethod
    def lade_naechste_probe():
        pfad = APP_CONFIG["files"]["naechste_probe"]
        if not os.path.exists(pfad):
            return []
        with open(pfad, encoding="utf-8") as f:
            return [z.strip() for z in f if z.strip()]

    @staticmethod
    def speichere_naechste_probe(songs):
        try:
            inhalt = "\n".join(songs) + ("\n" if songs else "")
            return DataManager._schreibe_mit_sync(
                APP_CONFIG["files"]["naechste_probe"],
                inhalt,
                "Auswahl fuer die naechste Probe",
            )
        except Exception as e:
            st.error(f"Auswahl konnte nicht gespeichert werden: {e}")
            return False
