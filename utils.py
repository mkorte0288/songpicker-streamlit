import os
import zipfile
from datetime import datetime
from config import APP_CONFIG

def backup_dateien():
    """Erstellt ein ZIP-Backup der Song- und History-Dateien"""
    os.makedirs(APP_CONFIG["files"]["backup_dir"], exist_ok=True)
    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    backup_path = os.path.join(APP_CONFIG["files"]["backup_dir"], backup_name)
    with zipfile.ZipFile(backup_path, 'w') as zipf:
        for fname in [APP_CONFIG["files"]["songs"], APP_CONFIG["files"]["history"]]:
            if os.path.exists(fname):
                zipf.write(fname)
    return backup_path

def color_for_reifegrad(grad):
    """
    Gibt eine Farbe im Verlauf Rot (0) -> Gelb (5) -> Grün (10) für den Reifegrad zurück.
    """
    # Clamp grad
    grad = max(0, min(10, grad))
    if grad <= 5:
        # Rot (252, 80, 80) -> Gelb (252, 223, 31)
        r = 252
        g = int(80 + (223-80) * (grad/5))
        b = int(80 + (31-80) * (grad/5))
    else:
        # Gelb (252, 223, 31) -> Grün (60, 179, 113)
        r = int(252 + (60-252) * ((grad-5)/5))
        g = int(223 + (179-223) * ((grad-5)/5))
        b = int(31 + (113-31) * ((grad-5)/5))
    return f'rgb({r},{g},{b})'

def kommentar_fuer_reifegrad(grad):
    if grad < 4:
        return "Übungsbedarf!"
    elif grad >= 9:
        return "Top fit!"
    else:
        return ""

def color_for_reifegrad_mpl(grad):
    """
    Gibt eine Farbe als (r,g,b)-Tupel (Werte 0-1) für Matplotlib zurück.
    """
    grad = max(0, min(10, grad))
    if grad <= 5:
        r = 252
        g = int(80 + (223-80) * (grad/5))
        b = int(80 + (31-80) * (grad/5))
    else:
        r = int(252 + (60-252) * ((grad-5)/5))
        g = int(223 + (179-223) * ((grad-5)/5))
        b = int(31 + (113-31) * ((grad-5)/5))
    return (r/255, g/255, b/255) 
