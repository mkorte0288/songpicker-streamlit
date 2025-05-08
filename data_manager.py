import pandas as pd
import os
from datetime import datetime
from config import APP_CONFIG
from utils import backup_dateien

class DataManager:
    """Verwaltet alle Datenoperationen für die App"""
    @staticmethod
    def lade_songliste():
        """Lädt die Songliste aus der CSV-Datei"""
        try:
            file_path = APP_CONFIG["files"]["songs"]
            if not os.path.exists(file_path):
                # Erstelle leere Datei mit Spaltenüberschriften
                df = pd.DataFrame(columns=['Songtitel', 'Zuletzt_gespielt', 'Reifegrad', 
                                           'Anzahl_gespielt', 'Kommentar', 'Tags', 'Must_Play'])
                df.to_csv(file_path, sep=';', index=False)
                return df
            
            df = pd.read_csv(file_path, sep=';', encoding='utf-8-sig')
            df.columns = df.columns.str.strip()
            required_columns = {
                'Songtitel': '',
                'Zuletzt_gespielt': pd.Timestamp('1900-01-01'),
                'Reifegrad': 5,
                'Anzahl_gespielt': 0,
                'Kommentar': '',
                'Tags': '',
                'Must_Play': False
            }
            for col, default in required_columns.items():
                if col not in df.columns:
                    df[col] = default
            df['Zuletzt_gespielt'] = pd.to_datetime(df['Zuletzt_gespielt'], errors='coerce').fillna(pd.Timestamp('1900-01-01'))
            df['Reifegrad'] = pd.to_numeric(df['Reifegrad'], errors='coerce').fillna(5).clip(0, 10).astype(int)
            df['Anzahl_gespielt'] = pd.to_numeric(df['Anzahl_gespielt'], errors='coerce').fillna(0).astype(int)
            df['Must_Play'] = df.get('Must_Play', False).astype(bool)
            return df
        except Exception as e:
            st.error(f"Fehler beim Laden der Songliste: {e}")
            columns = ['Songtitel', 'Zuletzt_gespielt', 'Reifegrad', 
                       'Anzahl_gespielt', 'Kommentar', 'Tags', 'Must_Play']
            return pd.DataFrame(columns=columns)
    
    @staticmethod
    def speichere_songliste(df):
        """Speichert die Songliste in der CSV-Datei mit automatischem Backup"""
        try:
            if os.path.exists(APP_CONFIG["files"]["songs"]):
                backup_dateien()
            # Sicherstellen, dass alle Spalten vorhanden sind
            required_columns = ['Songtitel', 'Zuletzt_gespielt', 'Reifegrad', 
                                'Anzahl_gespielt', 'Kommentar', 'Tags', 'Must_Play']
            for col in required_columns:
                if col not in df.columns:
                    df[col] = ''
            df.to_csv(APP_CONFIG["files"]["songs"], sep=';', index=False)
        except Exception as e:
            st.error(f"Fehler beim Speichern der Songliste: {e}")

    @staticmethod
    def lade_history():
        try:
            file_path = APP_CONFIG["files"]["history"]
            if not os.path.exists(file_path):
                return pd.DataFrame(columns=['Songtitel', 'Gespielt_am'])
            df = pd.read_csv(file_path, sep=';', encoding='utf-8-sig')
            df.columns = df.columns.str.strip()
            df['Gespielt_am'] = pd.to_datetime(df['Gespielt_am'], errors='coerce')
            return df
        except Exception as e:
            st.error(f"Fehler beim Laden der History: {e}")
            return pd.DataFrame(columns=['Songtitel', 'Gespielt_am'])

    @staticmethod
    def aktualisiere_history(songnamen, datum):
        try:
            df = pd.DataFrame({'Songtitel': songnamen, 'Gespielt_am': datum})
            df.to_csv(APP_CONFIG["files"]["history"], sep=';', mode='a', header=not os.path.exists(APP_CONFIG["files"]["history"]), index=False)
        except Exception as e:
            st.error(f"Fehler beim Aktualisieren der History: {e}") 