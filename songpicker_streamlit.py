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
from streamlit_echarts import st_echarts
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

from config import APP_CONFIG
from utils import color_for_reifegrad, kommentar_fuer_reifegrad, color_for_reifegrad_mpl
from data_manager import DataManager

# ======= EINRICHTUNG DER STREAMLIT-SEITE =======
st.set_page_config(
    page_title="Songpicker for Foo Fightclub", 
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

/* Header Layout */
.header-container {
    display: flex;
    align-items: center;
    gap: 20px;
    margin-bottom: 1rem;
}

.logo-image {
    height: 120px;
    width: auto;
    object-fit: contain;
}

.banner-image {
    height: 120px;
    width: auto;
    object-fit: contain;
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

NAECHSTE_PROBE_FILE = "naechste_probe.csv"

# ======= UI-START =======
if os.path.exists(APP_CONFIG["files"]["logo"]):
    st.image(APP_CONFIG["files"]["logo"], width=120)

st.title("Songpicker for Foo Fightclub")

# Tabs mit verbessertem Layout
probe_tabs = ["Nächste Probe"] + ["🎲 Auswahl", "📊 Analyse", "📜 History", "🎯 Nachbereitung", "✏️ Songliste bearbeiten"]
tabs = st.tabs(probe_tabs)
if 'tab_index' in st.session_state:
    st.experimental_set_query_params(tab=st.session_state['tab_index'])

# --- TAB 0: Nächste Probe ---
with tabs[0]:
    st.header("📝 Nächste Probe: Song-Übersicht")
    demo_user = "Demo-User"
    if os.path.exists(NAECHSTE_PROBE_FILE):
        with open(NAECHSTE_PROBE_FILE, "r", encoding="utf-8") as f:
            selected_songs = [line.strip() for line in f if line.strip()]
    else:
        selected_songs = []
    if not selected_songs:
        st.info("Es wurde noch keine Songauswahl für die nächste Probe gespeichert.")
    else:
        st.write(f"**Geplante Songs für die nächste Probe:**")
        if 'commitments' not in st.session_state:
            st.session_state['commitments'] = {}
        for song in selected_songs:
            key = f"commit_{song}"
            committed = st.session_state['commitments'].get(song, False)
            col1, col2 = st.columns([8, 1])
            with col1:
                st.write(f"- {song}")
            with col2:
                if st.button("👍" if not committed else "✅", key=key):
                    st.session_state['commitments'][song] = not committed
                    st.rerun()
                if committed:
                    st.caption(f"{demo_user} committed")

# --- TAB 1: Auswahl ---
with tabs[1]:
    # Band-Health-Meter (Gauge)
    st.markdown('<h3 style="text-align:center; margin-bottom: 0.5em;">Band-Health</h3>', unsafe_allow_html=True)
    songs_df = get_cached_songliste()
    avg_reifegrad = songs_df['Reifegrad'].mean() if not songs_df.empty else 0
    option = {
        "series": [
            {
                "type": "gauge",
                "startAngle": 210,
                "endAngle": -30,
                "min": 0,
                "max": 10,
                "progress": {"show": True, "width": 18},
                "axisLine": {
                    "lineStyle": {
                        "width": 18,
                        "color": [
                            [0.4, "#fc5454"],   # Rot
                            [0.8, "#fcdf1f"],   # Gelb
                            [1,   "#3cb371"]    # Grün
                        ]
                    }
                },
                "pointer": {"icon": "rect", "width": 8, "length": "70%", "offsetCenter": [0, "8%"]},
                "axisTick": {"show": False},
                "splitLine": {"show": False},
                "axisLabel": {"distance": 25, "fontSize": 14, "color": "#fafafa"},
                "detail": {
                    "valueAnimation": True,
                    "formatter": "{value} / 10",
                    "fontSize": 24,
                    "color": "#fafafa",
                    "backgroundColor": "#222a",
                    "borderRadius": 8,
                    "padding": [6, 12],
                    "offsetCenter": [0, '60%']
                },
                "data": [{"value": round(avg_reifegrad, 1)}]
            }
        ],
        "backgroundColor": "#0e1117"
    }
    st_echarts(option, height="260px")
    st.info("Das Band-Health-Meter zeigt den aktuellen durchschnittlichen Reifegrad aller Songs.")

    st.info("""
    **Song-Auswahl:**
    - Generiere eine Playlist für die nächste Probe nach verschiedenen Kriterien.
    - Passe Filter und Einstellungen an, um die Auswahl zu beeinflussen.
    - Speichere die Auswahl, um sie für die Probe zu übernehmen.
    """)
    st.header("🎲 Song-Auswahl für die nächste Probe")

    # Step 1: Filter
    with st.expander("1️⃣ Filter (Tags)", expanded=True):
        songs_df = get_cached_songliste()
        alle_tags = set()
        for tags in songs_df['Tags'].dropna():
            for tag in [t.strip() for t in str(tags).split(',') if t.strip()]:
                alle_tags.add(tag)
        alle_tags = sorted(alle_tags)
        selected_tags = st.multiselect("Nach Tags filtern", alle_tags, key="auswahl_tagfilter")

    # Step 2: Einstellungen
    with st.expander("2️⃣ Einstellungen", expanded=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            anzahl_songs = st.slider("Wie viele Songs sollen ausgewählt werden?", 3, 10, 5)
            spieldatum = st.date_input("📅 Datum der Probe", value=datetime.today())
    # Erweiterte Einstellungen als separater Expander, außerhalb und darunter
    with st.expander("Erweiterte Einstellungen", expanded=False):
        must_play_weight = st.slider("Gewichtung für Must-Play Songs", 1.0, 5.0, 2.0, 0.5,
                                    help="Bestimmt, wie stark Must-Play Songs bevorzugt werden")
        reifegrad_weight = st.slider("Gewichtung für Reifegrad", 0.5, 2.0, 1.0, 0.1,
                                    help="Bestimmt, wie stark der Reifegrad die Auswahl beeinflusst")

    # Step 3: Songauswahl & Aktionen
    with st.expander("3️⃣ Songauswahl & Aktionen", expanded=True):
        if songs_df.empty:
            st.error("Die Datei songliste.csv wurde nicht gefunden oder ist leer.")
        else:
            # Gewichtete Auswahl mit verbesserten Gewichtungen (wie vorher)
            max_days = (datetime.today() - songs_df['Zuletzt_gespielt']).dt.days.max()
            if max_days == 0: max_days = 1
            weights = (
                (11 - songs_df['Reifegrad']) * must_play_weight +
                (songs_df['Zuletzt_gespielt'].apply(lambda d: (datetime.today() - d).days) / max_days * 5) +
                (songs_df['Must_Play'] * reifegrad_weight)
            )
            weights = weights.clip(lower=0.1)
            weights = weights / weights.sum()
            selected_songs_container = st.container()
            if st.button("🎲 Songs auswählen", use_container_width=True, help="Erstellt eine neue zufällige Songauswahl nach den aktuellen Kriterien."):
                n_songs = min(anzahl_songs, len(songs_df))
                auswahl = songs_df.sample(n=n_songs, weights=weights, random_state=random.randint(0, 10000))
                st.session_state.selected_songs = auswahl['Songtitel'].tolist()
                st.rerun()
            if 'selected_songs' not in st.session_state:
                st.session_state.selected_songs = []
            with selected_songs_container:
                if st.session_state.selected_songs:
                    st.subheader("🎵 Ausgewählte Songs")
                    st.write(f"Anzahl ausgewählter Songs: {len(st.session_state.selected_songs)}")
                    for song in st.session_state.selected_songs:
                        song_data = songs_df[songs_df['Songtitel'] == song].iloc[0]
                        farbe = color_for_reifegrad(song_data['Reifegrad'])
                        status = kommentar_fuer_reifegrad(song_data['Reifegrad'])
                        must_play_badge = "⭐ " if song_data['Must_Play'] else ""
                        balken_breite = song_data['Reifegrad'] * 10  # Prozent
                        st.markdown(
                            f"""
                            <div style='padding: 10px; margin: 5px 0; border-radius: 5px; background-color: {farbe}20;'>
                                <span style='font-weight:bold'>{must_play_badge}{song}</span><br>
                                <div style='margin: 6px 0 2px 0; width: 100%; max-width: 300px; height: 16px; background: #2223; border-radius: 8px; position: relative;'>
                                    <div style='height: 100%; width: {balken_breite}%; background: {farbe}; border-radius: 8px;'></div>
                                    <span style='position: absolute; left: {balken_breite}%; top: 0; transform: translateX(-50%); font-size: 0.9em; color: #fff; font-weight: bold;'>{song_data['Reifegrad']}/10</span>
                                </div>
                                Reifegrad: {song_data['Reifegrad']} {status if status else ''}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    st.divider()
                    st.subheader("➕ Weitere Songs hinzufügen")
                    verfuegbare_songs = sorted(set(songs_df['Songtitel']) - set(st.session_state.selected_songs))
                    if verfuegbare_songs:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            neuer_song = st.selectbox("Song auswählen", verfuegbare_songs, key="add_song_select")
                        with col2:
                            if st.button("➕ Hinzufügen", use_container_width=True, help="Fügt den ausgewählten Song zur aktuellen Auswahl hinzu.", key="add_song_button"):
                                st.session_state.selected_songs.append(neuer_song)
                                st.rerun()
                        st.caption("Fügt den ausgewählten Song zur aktuellen Auswahl hinzu.")
                    else:
                        st.info("Alle Songs sind bereits ausgewählt.")
                    st.divider()
                    # Auswahl speichern Button
                    if st.button("💾 Auswahl speichern", use_container_width=True, help="Speichert die aktuelle Songauswahl für die nächste Probe."):
                        with open(NAECHSTE_PROBE_FILE, "w", encoding="utf-8") as f:
                            for song in st.session_state.selected_songs:
                                f.write(song + "\n")
                        st.success("Songauswahl für die nächste Probe gespeichert!")
                        st.rerun()

# --- TAB 2: Analyse ---
with tabs[2]:
    st.info("""
    **Analyse:**
    - Sieh dir Statistiken zu gespielten Songs und Reifegraden an.
    - Exportiere History und Songliste als CSV.
    """)
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
            farben = [color_for_reifegrad_mpl(reifegrad_map.get(song, 5)) for song in top.index]
            plt.style.use('dark_background')
            fig, ax = plt.subplots(figsize=(10, 6))
            fig.patch.set_facecolor('#0e1117')
            ax.set_facecolor('#0e1117')
            ax.tick_params(colors='#fafafa')
            ax.xaxis.label.set_color('#fafafa')
            ax.yaxis.label.set_color('#fafafa')
            ax.title.set_color('#fafafa')
            ax.barh(y=top.index, width=top.values, color=farben)
            ax.set_xlabel("Anzahl gespielt")
            ax.set_ylabel("Songtitel")
            plt.tight_layout()
            st.pyplot(fig)
        
        with col2:
            st.subheader("Reifegrad-Verteilung")
            plt.style.use('dark_background')
            fig, ax = plt.subplots(figsize=(10, 6))
            fig.patch.set_facecolor('#0e1117')
            ax.set_facecolor('#0e1117')
            ax.tick_params(colors='#fafafa')
            ax.xaxis.label.set_color('#fafafa')
            ax.yaxis.label.set_color('#fafafa')
            ax.title.set_color('#fafafa')
            songs_df['Reifegrad'].hist(bins=11, ax=ax, color='skyblue')
            ax.set_xlabel("Reifegrad")
            ax.set_ylabel("Anzahl Songs")
            plt.tight_layout()
            st.pyplot(fig)
        
        # Neue Metriken
        anzahl_proben = history_df['Gespielt_am'].dt.date.nunique()
        avg_songs_per_probe = history_df.shape[0] / anzahl_proben if anzahl_proben > 0 else 0
        meistgespielter_song = history_df['Songtitel'].value_counts().idxmax() if not history_df.empty else "-"
        # Längste Song-Pause
        last_played = songs_df.set_index('Songtitel')['Zuletzt_gespielt']
        heute = pd.to_datetime(datetime.today())
        song_pauses = (heute - last_played).dt.days
        song_with_longest_pause = song_pauses.idxmax() if not song_pauses.empty else "-"
        longest_pause_days = song_pauses.max() if not song_pauses.empty else 0
        avg_reifegrad = songs_df['Reifegrad'].mean()
        low_reifegrad_count = (songs_df['Reifegrad'] < 4).sum()
        never_played_count = songs_df['Anzahl_gespielt'].eq(0).sum()

        # KPIs wieder als klassische st.metric()-Werte anzeigen
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Anzahl Proben", anzahl_proben)
            st.metric("Ø Songs/Probe", f"{avg_songs_per_probe:.1f}")
            st.metric("Songs mit Reifegrad < 4", low_reifegrad_count)
        with col2:
            st.metric("Meistgespielter Song", meistgespielter_song)
            st.metric("Song mit längster Pause", f"{song_with_longest_pause} ({longest_pause_days} Tage)")
            st.metric("Songs nie gespielt", never_played_count)
        with col3:
            st.metric("Ø Reifegrad", f"{avg_reifegrad:.1f}")
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
with tabs[3]:
    st.info("""
    **History:**
    - Durchsuche und filtere die Spielhistorie nach Datum.
    - Lade vergangene Proben als Tabelle herunter.
    """)
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
with tabs[4]:
    st.info("""
    **Nachbereitung:**
    - Passe Reifegrade und Kommentare für die letzte Probe an.
    - Entferne oder ergänze Songs für die Probe.
    """)
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
            # Speichere entfernte Songs für Undo
            if 'undo_removed_songs' not in st.session_state:
                st.session_state['undo_removed_songs'] = []
            for removed_song in songs_to_remove:
                removed_row = history_df[(history_df['Songtitel'] == removed_song) & (history_df['Gespielt_am'].dt.date == auswahl_datum)]
                if not removed_row.empty:
                    st.session_state['undo_removed_songs'].append(removed_row.iloc[0].to_dict())
            history_df = history_df[~((history_df['Songtitel'].isin(songs_to_remove)) & (history_df['Gespielt_am'].dt.date == auswahl_datum))]
            history_df.to_csv(APP_CONFIG["files"]["history"], sep=';', index=False)
            st.success(f"{', '.join(songs_to_remove)} aus der Probe am {auswahl_datum} entfernt.")
            st.rerun()

            # Undo-Button anzeigen, falls Songs entfernt wurden
            if st.session_state.get('undo_removed_songs'):
                if st.button("Rückgängig machen (letzten entfernten Song wiederherstellen)"):
                    last_removed = st.session_state['undo_removed_songs'].pop()
                    # Füge den Song wieder zur History hinzu
                    df = pd.DataFrame([last_removed])
                    df.to_csv(APP_CONFIG["files"]["history"], sep=';', mode='a', header=False, index=False)
                    st.success(f"Song '{last_removed['Songtitel']}' wurde wiederhergestellt.")
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
with tabs[5]:
    st.info("""
    **Songliste bearbeiten:**
    - Bearbeite, ergänze oder lösche Songs direkt in der Tabelle.
    - Füge neue Songs hinzu oder exportiere die Liste.
    - Markiere Songs als Favorit ⭐ und hinterlege individuelle Notizen.
    """)
    st.header("✏️ Songliste bearbeiten")
    # Backup-Button jetzt hier:
    if st.button("🔄 Backup erstellen"):
        backup_path = backup_dateien()
        st.success(f"Backup erstellt: {os.path.basename(backup_path)}")
    songs_df = get_cached_songliste()

    # Stelle sicher, dass Kommentar und Notiz als String vorliegen
    if 'Kommentar' in songs_df:
        songs_df['Kommentar'] = songs_df['Kommentar'].astype(str)
    if 'Tags' in songs_df:
        songs_df['Tags'] = songs_df['Tags'].astype(str)
    if 'Notiz' not in songs_df:
        songs_df['Notiz'] = ""
    if 'Favorit' not in songs_df:
        songs_df['Favorit'] = False

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
            "Favorit": st.column_config.CheckboxColumn("Favorit ⭐", required=False),
            "Notiz": st.column_config.TextColumn("Notiz", required=False),
        },
        hide_index=True,
        key="songliste_editor"
    )

    # Änderungen speichern
    if st.button("💾 Änderungen speichern", key="save_songlist_edits"):
        edited_df = edited_df[edited_df['Songtitel'].str.strip() != ""]
        if 'Zuletzt_gespielt' in edited_df:
            edited_df['Zuletzt_gespielt'] = pd.to_datetime(edited_df['Zuletzt_gespielt'], errors='coerce')
        if 'Reifegrad' in edited_df:
            edited_df['Reifegrad'] = pd.to_numeric(edited_df['Reifegrad'], errors='coerce').fillna(5).astype(int)
        if 'Anzahl_gespielt' in edited_df:
            edited_df['Anzahl_gespielt'] = pd.to_numeric(edited_df['Anzahl_gespielt'], errors='coerce').fillna(0).astype(int)
        if 'Must_Play' in edited_df:
            edited_df['Must_Play'] = edited_df['Must_Play'].fillna(False).astype(bool)
        if 'Favorit' in edited_df:
            edited_df['Favorit'] = edited_df['Favorit'].fillna(False).astype(bool)
        DataManager.speichere_songliste(edited_df)
        st.success("Songliste erfolgreich gespeichert.")
        st.rerun()

# --- Nach oben Button (global, sticky unten rechts) ---
scroll_to_top_html = '''
<style>
#scrollToTopBtn {
    display: none;
    position: fixed;
    bottom: 32px;
    right: 32px;
    z-index: 9999;
    background: #ffe066;
    color: #222;
    border: none;
    border-radius: 50%;
    width: 48px;
    height: 48px;
    font-size: 2rem;
    box-shadow: 0 2px 8px #0003;
    cursor: pointer;
    transition: background 0.2s;
}
#scrollToTopBtn:hover {
    background: #ffd700;
}
</style>
<button id="scrollToTopBtn" onclick="window.scrollTo({top: 0, behavior: 'smooth'});">⬆️</button>
<script>
window.onscroll = function() {
    var btn = document.getElementById("scrollToTopBtn");
    if (!btn) return;
    if (document.body.scrollTop > 300 || document.documentElement.scrollTop > 300) {
        btn.style.display = "block";
    } else {
        btn.style.display = "none";
    }
};
</script>
'''
st.markdown(scroll_to_top_html, unsafe_allow_html=True)
