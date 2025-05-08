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
    if grad < 4:
        return APP_CONFIG["colors"]["low"]
    elif grad >= 9:
        return APP_CONFIG["colors"]["high"]
    else:
        return APP_CONFIG["colors"]["medium"]

def kommentar_fuer_reifegrad(grad):
    if grad < 4:
        return "Übungsbedarf!"
    elif grad >= 9:
        return "Top fit!"
    else:
        return "" 