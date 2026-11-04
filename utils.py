import os
from io import BytesIO
import zipfile
from datetime import datetime

import pandas as pd

from config import APP_CONFIG

_T = APP_CONFIG["reifegrad"]


def backup_dateien():
    """Erstellt ein ZIP-Backup der Song- und History-Dateien."""
    os.makedirs(APP_CONFIG["files"]["backup_dir"], exist_ok=True)
    name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    pfad = os.path.join(APP_CONFIG["files"]["backup_dir"], name)
    with zipfile.ZipFile(pfad, "w", zipfile.ZIP_DEFLATED) as z:
        for f in (APP_CONFIG["files"]["songs"], APP_CONFIG["files"]["history"]):
            if os.path.exists(f):
                z.write(f)
    return pfad


def parse_datum(serie):
    """Datumsspalten formatabhängig einlesen.

    Die beiden CSV-Dateien benutzen unterschiedliche Schreibweisen:
    spielhistorie.csv steht in ISO (2025-05-08), songliste.csv in
    Tag/Monat/Jahr (08/05/2025). Ein pauschales dayfirst=True zerlegt
    die ISO-Daten (aus 2025-05-10 wird der 5. Oktober), ein pauschales
    dayfirst=False vertauscht die anderen. Deshalb wird pro Spalte
    erkannt, welches Format vorliegt.
    """
    s = serie.astype(str).str.strip()
    iso = s.str.fullmatch(r"\d{4}-\d{2}-\d{2}([ T].*)?")
    ergebnis = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")
    if iso.any():
        ergebnis[iso] = pd.to_datetime(s[iso], errors="coerce", format="ISO8601")
    if (~iso).any():
        ergebnis[~iso] = pd.to_datetime(s[~iso], errors="coerce", dayfirst=True)
    return ergebnis


def _misch(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def reifegrad_rgb(grad):
    """Farbe im Verlauf rot -> gelb -> gruen als (r, g, b)."""
    grad = max(0, min(10, float(grad) if pd.notna(grad) else 0))
    low, mid, high = (_hex2rgb(_T["low"]), _hex2rgb(_T["mid"]), _hex2rgb(_T["high"]))
    return _misch(low, mid, grad / 5) if grad <= 5 else _misch(mid, high, (grad - 5) / 5)


def color_for_reifegrad(grad):
    r, g, b = reifegrad_rgb(grad)
    return f"rgb({r},{g},{b})"


def color_for_reifegrad_mpl(grad):
    r, g, b = reifegrad_rgb(grad)
    return (r / 255, g / 255, b / 255)


def kommentar_fuer_reifegrad(grad):
    if pd.isna(grad):
        return ""
    if grad < 4:
        return "Übungsbedarf"
    if grad >= 9:
        return "Sitzt"
    return ""


def spielzeit_in_sekunden(wert):
    """'4:31' -> 271. Leere oder unlesbare Werte -> 0."""
    try:
        teile = str(wert).strip().split(":")
        if len(teile) != 2:
            return 0
        return int(teile[0]) * 60 + int(teile[1])
    except (ValueError, AttributeError):
        return 0


def sekunden_als_text(sekunden):
    if not sekunden:
        return "–"
    return f"{sekunden // 60} min" if sekunden < 3600 else f"{sekunden // 3600} h {(sekunden % 3600) // 60} min"


def backup_als_zip():
    """Downloadbares Backup aller drei Datendateien ohne temporäre ZIP-Datei."""
    ausgabe = BytesIO()
    with zipfile.ZipFile(ausgabe, "w", zipfile.ZIP_DEFLATED) as archiv:
        for datei in (
            APP_CONFIG["files"]["songs"],
            APP_CONFIG["files"]["history"],
            APP_CONFIG["files"]["naechste_probe"],
        ):
            if os.path.exists(datei):
                archiv.write(datei, arcname=os.path.basename(datei))
    return ausgabe.getvalue()
