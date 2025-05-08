import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import random
import os
import io
import zipfile
import base64
import json

from config import APP_CONFIG
from utils import color_for_reifegrad, kommentar_fuer_reifegrad
from data_manager import DataManager

# ======= EINRICHTUNG DER STREAMLIT-SEITE =======
st.set_page_config(
    page_title=APP_CONFIG["title"], 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# ======= RESPONSIVE DESIGN =======
responsive_css = '''
<style>
/* Grundlegende Schriftgrößen und Abstände */
html, body, .stApp {
    font-size: 1.05rem;
}

/* Buttons und Inputs größer auf kleinen Bildschirmen */
@media (max-width: 700px) {
    .stButton > button, .stTextInput > div > input, .stSelectbox > div, .stSlider > div {
        font-size: 1.1rem !important;
        min-height: 48px !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        flex-direction: column !important;
    }
    .stTabs [data-baseweb="tab"] {
        width: 100% !important;
        margin-bottom: 4px;
    }
    .stColumn {
        flex-basis: 100% !important;
        max-width: 100% !important;
        min-width: 100% !important;
    }
    .stDataFrameContainer, .stDataFrame, .stDataEditorContainer {
        font-size: 1rem !important;
    }
}

/* Tabelle und DataEditor auf kleinen Bildschirmen */
@media (max-width: 500px) {
    .stDataFrameContainer, .stDataFrame, .stDataEditorContainer {
        font-size: 0.95rem !important;
    }
}
</style>
'''
st.markdown(responsive_css, unsafe_allow_html=True)

# Cache für häufig verwendete Daten
@st.cache_data(ttl=300)  # Cache für 5 Minuten
def get_cached_songliste():
    return DataManager.lade_songliste()

@st.cache_data(ttl=300)
def get_cached_history():
    return DataManager.lade_history()

# ======= UI-START =======
if os.path.exists(APP_CONFIG["files"]["logo"]):
    st.image(APP_CONFIG["files"]["logo"], width=120)

st.title(APP_CONFIG["title"])

# Tabs mit verbessertem Layout
tabs = st.tabs(["🎲 Auswahl", "📊 Analyse", "📜 History", "🎯 Nachbereitung", "✏️ Songliste bearbeiten"])

# --- TAB 1: Auswahl ---
with tabs[0]:
    st.header("🎲 Song-Auswahl für die nächste Probe")
    
    # Songpicker-Einstellungen
    col1, col2 = st.columns([2, 1])
    with col1:
        anzahl_songs = st.slider("Wie viele Songs sollen ausgewählt werden?", 3, 10, 5)
        spieldatum = st.date_input("📅 Datum der Probe", value=datetime.today())
    
    with st.expander("🎯 Erweiterte Einstellungen", expanded=False):
        must_play_weight = st.slider("Gewichtung für Must-Play Songs", 1.0, 5.0, 2.0, 0.5,
                                    help="Bestimmt, wie stark Must-Play Songs bevorzugt werden")
        reifegrad_weight = st.slider("Gewichtung für Reifegrad", 0.5, 2.0, 1.0, 0.1,
                                    help="Bestimmt, wie stark der Reifegrad die Auswahl beeinflusst")
    
    songs_df = get_cached_songliste()
    
    # Tag-Filter
    alle_tags = set()
    for tags in songs_df['Tags'].dropna():
        for tag in [t.strip() for t in str(tags).split(',') if t.strip()]:
            alle_tags.add(tag)
    alle_tags = sorted(alle_tags)
    selected_tags = st.multiselect("Nach Tags filtern", alle_tags, key="auswahl_tagfilter")
    if selected_tags:
        songs_df = songs_df[songs_df['Tags'].apply(lambda x: any(tag in str(x).split(',') for tag in selected_tags))]

    if songs_df.empty:
        st.error("Die Datei songliste.csv wurde nicht gefunden oder ist leer.")
    else:
        # Gewichtete Auswahl mit verbesserten Gewichtungen
        max_days = (datetime.today() - songs_df['Zuletzt_gespielt']).dt.days.max()
        if max_days == 0: max_days = 1
        
        # Verbesserte Gewichtungslogik
        weights = (
            (11 - songs_df['Reifegrad']) * reifegrad_weight +  # Reifegrad-Gewichtung
            (songs_df['Zuletzt_gespielt'].apply(lambda d: (datetime.today() - d).days) / max_days * 5) +  # Zeit-Gewichtung
            (songs_df['Must_Play'] * must_play_weight)  # Must-Play Gewichtung
        )
        weights = weights.clip(lower=0.1)
        weights = weights / weights.sum()
        
        # Container für die ausgewählten Songs
        selected_songs_container = st.container()
        
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🎲 Songs auswählen", use_container_width=True):
                # Stelle sicher, dass wir nicht mehr Songs auswählen als verfügbar sind
                n_songs = min(anzahl_songs, len(songs_df))
                
                # Debug-Ausgabe
                st.write(f"Anzahl zu wählender Songs: {n_songs}")
                st.write(f"Verfügbare Songs: {len(songs_df)}")
                
                # Wähle Songs aus
                auswahl = songs_df.sample(n=n_songs, weights=weights, random_state=random.randint(0, 10000))
                
                # Debug-Ausgabe
                st.write(f"Anzahl ausgewählter Songs: {len(auswahl)}")
                st.write("Ausgewählte Songs:", auswahl['Songtitel'].tolist())
                
                # Speichere die Auswahl
                st.session_state.selected_songs = auswahl['Songtitel'].tolist()
                st.rerun()
        
        with col1:
            st.info("""
            **Auswahlkriterien:**
            - Songs mit niedrigem Reifegrad werden bevorzugt
            - Songs, die lange nicht gespielt wurden, werden bevorzugt
            - Must-Play Songs werden stärker gewichtet
            - Die Gewichtung kann in den Einstellungen angepasst werden
            """)
        
        # Initialisiere selected_songs in session_state falls noch nicht vorhanden
        if 'selected_songs' not in st.session_state:
            st.session_state.selected_songs = []
        
        # Zeige ausgewählte Songs an
        with selected_songs_container:
            if st.session_state.selected_songs:
                st.subheader("🎵 Ausgewählte Songs")
                st.write(f"Anzahl ausgewählter Songs: {len(st.session_state.selected_songs)}")
                for song in st.session_state.selected_songs:
                    song_data = songs_df[songs_df['Songtitel'] == song].iloc[0]
                    farbe = color_for_reifegrad(song_data['Reifegrad'])
                    status = kommentar_fuer_reifegrad(song_data['Reifegrad'])
                    must_play_badge = "⭐ " if song_data['Must_Play'] else ""
                    st.markdown(
                        f"""
                        <div style='padding: 10px; margin: 5px 0; border-radius: 5px; background-color: {farbe}20;'>
                            <span style='font-weight:bold'>{must_play_badge}{song}</span><br>
                            Reifegrad: {song_data['Reifegrad']} {status if status else ''}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                
                # Info-Block für den Nutzer
                st.info(
                    """
                    **Was passiert als Nächstes?**
                    - Prüfe die ausgewählten Songs.
                    - Du kannst weitere Songs hinzufügen oder die Auswahl anpassen.
                    - Klicke auf **„Auswahl speichern“**, um die Songs für die nächste Probe zu übernehmen.
                    - Nach dem Speichern werden die Songs als gespielt markiert und in die History übernommen.
                    """
                )
                
                # Manuelle Song-Hinzufügung
                st.divider()
                st.subheader("➕ Weitere Songs hinzufügen")
                verfuegbare_songs = sorted(set(songs_df['Songtitel']) - set(st.session_state.selected_songs))
                if verfuegbare_songs:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        neuer_song = st.selectbox("Song auswählen", verfuegbare_songs, key="add_song_select")
                    with col2:
                        if st.button("➕ Hinzufügen", use_container_width=True):
                            st.session_state.selected_songs.append(neuer_song)
                            st.rerun()
                else:
                    st.info("Alle Songs sind bereits ausgewählt.")
                
                # Speichern der Auswahl
                if st.button("💾 Auswahl speichern", use_container_width=True):
                    heute = spieldatum.strftime('%Y-%m-%d')
                    songs_df.loc[songs_df['Songtitel'].isin(st.session_state.selected_songs), 'Zuletzt_gespielt'] = heute
                    songs_df.loc[songs_df['Songtitel'].isin(st.session_state.selected_songs), 'Anzahl_gespielt'] += 1
                    DataManager.speichere_songliste(songs_df)
                    DataManager.aktualisiere_history(st.session_state.selected_songs, heute)
                    st.success(f"{len(st.session_state.selected_songs)} Songs für den {heute} gespeichert.")
                    st.session_state.selected_songs = []  # Reset selection after saving
                    st.rerun()

# --- TAB 2: Analyse ---
with tabs[1]:
    st.header("📊 Analyse")
    history_df = get_cached_history()
    songs_df = get_cached_songliste()
    
    if history_df.empty or songs_df.empty:
        st.warning("Nicht genügend Daten für Analyse.")
    else:
        # Verbesserte Analyse mit mehr Visualisierungen
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Meistgespielte Songs (Top 10)")
            top = history_df['Songtitel'].value_counts().head(10)
            reifegrad_map = songs_df.set_index('Songtitel')['Reifegrad'].to_dict()
            farben = [color_for_reifegrad(reifegrad_map.get(song, 5)) for song in top.index]
            
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.barh(y=top.index, width=top.values, color=farben)
            ax.set_xlabel("Anzahl gespielt")
            ax.set_ylabel("Songtitel")
            plt.tight_layout()
            st.pyplot(fig)
        
        with col2:
            st.subheader("Reifegrad-Verteilung")
            fig, ax = plt.subplots(figsize=(10, 6))
            songs_df['Reifegrad'].hist(bins=11, ax=ax, color='skyblue')
            ax.set_xlabel("Reifegrad")
            ax.set_ylabel("Anzahl Songs")
            plt.tight_layout()
            st.pyplot(fig)
        
        # Neue Metriken
        col1, col2, col3 = st.columns(3)
        with col1:
            avg = songs_df['Reifegrad'].mean()
            st.metric("Durchschnittlicher Reifegrad", f"{avg:.1f}")
        with col2:
            total_plays = history_df.shape[0]
            st.metric("Gesamtanzahl Proben", total_plays)
        with col3:
            unique_songs = len(songs_df)
            st.metric("Anzahl Songs in Liste", unique_songs)
        
        # Export-Optionen
        st.subheader("📤 Export")
        col1, col2 = st.columns(2)
        with col1:
            csv = history_df.to_csv(index=False, sep=';').encode('utf-8-sig')
            st.download_button("History als CSV herunterladen", data=csv, 
                             file_name="spielhistorie_export.csv", mime="text/csv")
        with col2:
            csv = songs_df.to_csv(index=False, sep=';').encode('utf-8-sig')
            st.download_button("Songliste als CSV herunterladen", data=csv,
                             file_name="songliste_export.csv", mime="text/csv")

# --- TAB 3: History ---
with tabs[2]:
    st.header("📜 History")
    history_df = get_cached_history()
    
    if history_df.empty:
        st.info("Noch keine History-Daten vorhanden.")
    else:
        # Verbesserte Filterung
        col1, col2 = st.columns(2)
        with col1:
            jahr = st.selectbox("Filter nach Jahr", 
                              options=["Alle"] + sorted(history_df['Gespielt_am'].dt.year.dropna().unique().astype(str)))
        with col2:
            monat = st.selectbox("Filter nach Monat", 
                               options=["Alle"] + [str(m) for m in range(1, 13)])
        
        filtered_df = history_df.copy()
        if jahr != "Alle":
            filtered_df = filtered_df[filtered_df['Gespielt_am'].dt.year == int(jahr)]
        if monat != "Alle":
            filtered_df = filtered_df[filtered_df['Gespielt_am'].dt.month == int(monat)]
        
        # Verbesserte Darstellung
        st.dataframe(
            filtered_df.sort_values(by="Gespielt_am", ascending=False),
            use_container_width=True,
            column_config={
                "Gespielt_am": st.column_config.DatetimeColumn(
                    "Datum",
                    format="DD.MM.YYYY"
                )
            }
        )

# --- TAB 4: Nachbereitung ---
with tabs[3]:
    st.header("🎯 Nachbereitung der letzten Probe")
    history_df = get_cached_history()
    songs_df = get_cached_songliste()
    
    if history_df.empty or songs_df.empty:
        st.info("Noch keine Spieldaten vorhanden.")
    else:
        # Verbesserte Datumsauswahl
        datum_optionen = sorted(history_df['Gespielt_am'].dropna().dt.date.unique(), reverse=True)
        auswahl_datum = st.selectbox("📅 Probedatum auswählen", datum_optionen, key="nachbereitung_probedatum_select")
        
        # --- Song entfernen ---
        if 'songs_to_remove' not in st.session_state:
            st.session_state.songs_to_remove = []
        
        # --- Song hinzufügen ---
        weitere_songs = sorted(set(songs_df['Songtitel']) - set(history_df[history_df['Gespielt_am'].dt.date == auswahl_datum]['Songtitel']))
        st.divider()
        st.subheader("➕ Weiteren Song dieser Probe hinzufügen")
        if weitere_songs:
            col1, col2 = st.columns([3, 1])
            with col1:
                neuer_song = st.selectbox("Song aus Songliste auswählen", weitere_songs, key="neuer_probe_song")
            with col2:
                if st.button("➕ Song hinzufügen", use_container_width=True):
                    neue_zeile = pd.DataFrame({'Songtitel': [neuer_song], 'Gespielt_am': [pd.to_datetime(auswahl_datum)]})
                    neue_zeile.to_csv(APP_CONFIG["files"]["history"], sep=';', mode='a', header=False, index=False)
                    st.success(f"{neuer_song} wurde zur Probe am {auswahl_datum} hinzugefügt.")
                    st.rerun()
        else:
            st.info("Alle Songs dieser Probe sind bereits gelistet.")
        
        # --- History und gespielt nach jedem Hinzufügen/Entfernen neu laden ---
        history_df = pd.read_csv(APP_CONFIG["files"]["history"], sep=';', parse_dates=["Gespielt_am"])  # immer aktuell laden
        gespielt = history_df[history_df['Gespielt_am'].dt.date == auswahl_datum]
        gespielt = gespielt.merge(songs_df[['Songtitel', 'Reifegrad', 'Kommentar']], on='Songtitel', how='left')

        st.write("🎵 Gespielte Songs und Anpassung:")
        neue_werte = []
        songs_to_remove = []
        for i, row in gespielt.iterrows():
            with st.expander(f"📝 {row['Songtitel']}", expanded=True):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    grad = st.slider("Reifegrad", 0, 10, int(row['Reifegrad']) if not pd.isna(row['Reifegrad']) else 5, key=f"grad_{i}")
                with col2:
                    kommentar = st.text_input("Kommentar", value=row.get("Kommentar", ""), key=f"kommentar_{i}")
                with col3:
                    if st.button("❌ Entfernen", key=f"remove_{i}"):
                        songs_to_remove.append(row['Songtitel'])
            neue_werte.append((row['Songtitel'], grad, kommentar))

        # Entferne Songs aus der History, falls gewünscht
        if songs_to_remove:
            history_df = history_df[~((history_df['Songtitel'].isin(songs_to_remove)) & (history_df['Gespielt_am'].dt.date == auswahl_datum))]
            history_df.to_csv(APP_CONFIG["files"]["history"], sep=';', index=False)
            st.success(f"{', '.join(songs_to_remove)} aus der Probe am {auswahl_datum} entfernt.")
            st.rerun()
        
        if gespielt.shape[0] > 0:
            if st.button("💾 Änderungen speichern"):
                for titel, grad, kommentar in neue_werte:
                    idx = songs_df[songs_df['Songtitel'] == titel].index
                    if not idx.empty:
                        songs_df.loc[idx, 'Reifegrad'] = grad
                        songs_df.loc[idx, 'Kommentar'] = kommentar
                DataManager.speichere_songliste(songs_df)
                st.success("Änderungen erfolgreich gespeichert.")

# --- TAB 5: Songliste bearbeiten ---
with tabs[4]:
    st.header("✏️ Songliste bearbeiten")
    # Backup-Button jetzt hier:
    if st.button("🔄 Backup erstellen"):
        backup_path = backup_dateien()
        st.success(f"Backup erstellt: {os.path.basename(backup_path)}")
    songs_df = get_cached_songliste()

    # Stelle sicher, dass Kommentar als String vorliegt
    if 'Kommentar' in songs_df:
        songs_df['Kommentar'] = songs_df['Kommentar'].astype(str)

    # Tag-Filter
    alle_tags = set()
    for tags in songs_df['Tags'].dropna():
        for tag in [t.strip() for t in str(tags).split(',') if t.strip()]:
            alle_tags.add(tag)
    alle_tags = sorted(alle_tags)
    selected_tags = st.multiselect("Nach Tags filtern", alle_tags, key="bearbeiten_tagfilter")
    filtered_df = songs_df.copy()
    if selected_tags:
        filtered_df = filtered_df[filtered_df['Tags'].apply(lambda x: any(tag in str(x).split(',') for tag in selected_tags))]

    st.info("Du kannst die Songliste direkt in der Tabelle bearbeiten. Neue Songs als neue Zeile hinzufügen, Zeilen löschen, Felder anpassen. Klicke anschließend auf 'Änderungen speichern'.")

    # Data Editor für die Songliste
    edited_df = st.data_editor(
        filtered_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Songtitel": st.column_config.TextColumn("Songtitel", required=True),
            "Zuletzt_gespielt": st.column_config.DatetimeColumn("Zuletzt gespielt", format="DD.MM.YYYY", required=False),
            "Reifegrad": st.column_config.NumberColumn("Reifegrad", min_value=0, max_value=10, step=1),
            "Anzahl_gespielt": st.column_config.NumberColumn("Anzahl gespielt", min_value=0, step=1),
            "Kommentar": st.column_config.TextColumn("Kommentar", required=False),
            "Tags": st.column_config.TextColumn("Tags", required=False),
            "Must_Play": st.column_config.CheckboxColumn("Must-Play", required=False),
        },
        hide_index=True,
        key="songliste_editor"
    )

    # Änderungen speichern
    if st.button("💾 Änderungen speichern", key="save_songlist_edits"):
        # Entferne Zeilen ohne Songtitel
        edited_df = edited_df[edited_df['Songtitel'].str.strip() != ""]
        # Setze leere Felder auf Standardwerte
        if 'Zuletzt_gespielt' in edited_df:
            edited_df['Zuletzt_gespielt'] = pd.to_datetime(edited_df['Zuletzt_gespielt'], errors='coerce')
        if 'Reifegrad' in edited_df:
            edited_df['Reifegrad'] = pd.to_numeric(edited_df['Reifegrad'], errors='coerce').fillna(5).astype(int)
        if 'Anzahl_gespielt' in edited_df:
            edited_df['Anzahl_gespielt'] = pd.to_numeric(edited_df['Anzahl_gespielt'], errors='coerce').fillna(0).astype(int)
        if 'Must_Play' in edited_df:
            edited_df['Must_Play'] = edited_df['Must_Play'].fillna(False).astype(bool)
        # Speichere die Änderungen in die komplette Songliste zurück
        # Aktualisiere nur die Zeilen, die im Filter sichtbar waren
        # (Optional: Du kannst auch alle Zeilen ersetzen, falls gewünscht)
        songs_df.update(edited_df)
        DataManager.speichere_songliste(songs_df)
        st.success("Songliste erfolgreich gespeichert.")
        st.rerun()
