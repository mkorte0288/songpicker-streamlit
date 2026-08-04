"""Songpicker für Foo Fightclub.

Nur-Lesen für die Band, Bearbeitung lokal durch eine Person.
Bearbeitungsmodus: SONGPICKER_EDIT=1 streamlit run songpicker_streamlit.py
"""

import os
import random
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

import github_speicher
from config import APP_CONFIG, EDIT_ENV
from data_manager import DataManager
from utils import (
    backup_dateien,
    color_for_reifegrad,
    color_for_reifegrad_mpl,
    kommentar_fuer_reifegrad,
    sekunden_als_text,
    spielzeit_in_sekunden,
)


def grad_text(w):
    return "–" if pd.isna(w) else f"{int(w)} / 10"


def setlaenge(df, titel):
    return sekunden_als_text(
        sum(spielzeit_in_sekunden(v) for v in df[df["Songtitel"].isin(titel)]["Spielzeit"])
    )

T = APP_CONFIG["theme"]

st.set_page_config(
    page_title="Songpicker – Foo Fightclub",
    page_icon="🎸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------- Design
st.markdown(
    f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
<style>
  :root {{
    --ink: {T['ink']}; --ink-2: {T['ink_2']}; --paper: {T['paper']};
    --red: {T['red']}; --red-bright: {T['red_bright']}; --muted: {T['muted']};
    --line: {T['line']};
  }}
  .stApp {{ background: var(--ink); color: var(--paper);
            font-family: "Inter", system-ui, sans-serif; }}
  h1, h2, h3 {{ font-family: "Anton", Impact, sans-serif !important;
                font-weight: 400 !important; text-transform: uppercase;
                letter-spacing: -.02em; line-height: .95; }}
  h1 {{ font-size: clamp(44px, 6vw, 76px) !important; }}
  .ffc-eyebrow {{ color: var(--red-bright); font-size: 12px; font-weight: 900;
                  letter-spacing: .18em; text-transform: uppercase; margin-bottom: 6px; }}
  .stButton > button {{
      background: var(--red); color: #fff; border: 1px solid var(--red);
      border-radius: 0; min-height: 46px; font-weight: 900; font-size: 13px;
      letter-spacing: .08em; text-transform: uppercase; transition: transform .15s ease; }}
  .stButton > button:hover {{ background: #e65343; border-color: #e65343;
                              color: #fff; transform: translateY(-2px); }}
  .stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid var(--line); }}
  .stTabs [data-baseweb="tab"] {{ background: transparent; border-radius: 0;
      font-weight: 800; font-size: 13px; letter-spacing: .06em; text-transform: uppercase; }}
  .stTabs [aria-selected="true"] {{ border-bottom: 2px solid var(--red-bright); }}
  div[data-testid="stMetric"] {{ background: var(--ink-2); border: 1px solid var(--line);
      padding: 16px 18px; }}
  div[data-testid="stMetricValue"] {{ font-family: "Anton", sans-serif; font-weight: 400; }}
  .ffc-card {{ background: var(--ink-2); border: 1px solid var(--line);
               border-left: 3px solid var(--red); padding: 14px 16px; margin-bottom: 8px; }}
  .ffc-song {{ font-weight: 900; font-size: 16px; letter-spacing: .01em; }}
  .ffc-bar {{ height: 8px; background: rgba(231,222,209,.14); margin: 9px 0 5px; }}
  .ffc-bar > div {{ height: 100%; }}
  .ffc-meta {{ color: var(--muted); font-size: 12px; font-weight: 700;
               letter-spacing: .06em; text-transform: uppercase; }}
  .ffc-banner {{ border-left: 3px solid var(--red-bright); background: rgba(255,101,80,.08);
                 padding: 12px 16px; margin-bottom: 18px; font-size: 14px; }}
  @media (max-width: 700px) {{
    .stTabs [data-baseweb="tab-list"] {{ flex-wrap: wrap; }}
    .stButton > button {{ width: 100%; }}
  }}
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300)
def songs():
    return DataManager.songliste_mit_historie()


@st.cache_data(ttl=300)
def history():
    return DataManager.lade_history()


def frisch():
    st.cache_data.clear()


# ---------------------------------------------------------------- Kopf
kopf_links, kopf_rechts = st.columns([1, 6])
with kopf_links:
    if os.path.exists(APP_CONFIG["files"]["logo"]):
        st.image(APP_CONFIG["files"]["logo"], width=96)
with kopf_rechts:
    st.markdown('<p class="ffc-eyebrow">Proberaum-Werkzeug</p>', unsafe_allow_html=True)
    st.markdown("# Songpicker")

# ---------------------------------------------------------------- Anmeldung
# Standard: nur lesen. Bearbeiten entweder lokal per Umgebungsvariable
# oder im Browser per Passwort aus den Streamlit-Secrets.
if "darf_bearbeiten" not in st.session_state:
    st.session_state.darf_bearbeiten = EDIT_ENV

with st.sidebar:
    st.markdown("### Zugang")
    if st.session_state.darf_bearbeiten:
        st.success("Bearbeiten aktiv")
        if github_speicher.verfuegbar():
            st.caption("Änderungen werden ins GitHub-Repository committet.")
        else:
            st.warning(
                "Kein GitHub-Token hinterlegt. Änderungen gelten nur für diese "
                "Sitzung und sind beim nächsten Neustart weg."
            )
        if not EDIT_ENV and st.button("Abmelden", use_container_width=True):
            st.session_state.darf_bearbeiten = False
            st.rerun()
    elif github_speicher.passwort_gesetzt():
        eingabe = st.text_input("Passwort", type="password",
                                label_visibility="collapsed", placeholder="Passwort")
        if st.button("Anmelden", use_container_width=True):
            if github_speicher.pruefe_passwort(eingabe):
                st.session_state.darf_bearbeiten = True
                st.rerun()
            else:
                st.error("Passwort stimmt nicht.")
    else:
        st.caption("Nur-Lesen-Ansicht.")

EDIT_MODE = st.session_state.darf_bearbeiten

if not EDIT_MODE:
    st.markdown(
        '<div class="ffc-banner"><b>Nur-Lesen.</b> Das ist die Ansicht für die Band: '
        "was für die nächste Probe ansteht, wie der Stand der Songs ist und was "
        "wann gespielt wurde. Bearbeitet wird an einer Stelle.</div>",
        unsafe_allow_html=True,
    )

namen = ["Nächste Probe", "Analyse", "History"]
if EDIT_MODE:
    namen += ["Auswahl", "Nachbereitung", "Songliste"]
tabs = st.tabs(namen)

# ---------------------------------------------------------------- Nächste Probe
with tabs[0]:
    geplant = DataManager.lade_naechste_probe()
    df = songs()
    if not geplant:
        st.info("Für die nächste Probe ist noch keine Auswahl hinterlegt.")
    else:
        st.markdown("### Geplante Songs")
        for song in geplant:
            treffer = df[df["Songtitel"] == song]
            if treffer.empty:
                st.markdown(
                    f'<div class="ffc-card"><span class="ffc-song">{song}</span>'
                    '<div class="ffc-meta">nicht in der Songliste</div></div>',
                    unsafe_allow_html=True,
                )
                continue
            zeile = treffer.iloc[0]
            g = zeile["Reifegrad"]
            breite = 0 if pd.isna(g) else int(g) * 10
            farbe = "rgba(231,222,209,.25)" if pd.isna(g) else color_for_reifegrad(g)
            stern = "★ " if zeile["Must_Play"] else ""
            hinweis = kommentar_fuer_reifegrad(g)
            zeit = f" · {zeile['Spielzeit']}" if zeile["Spielzeit"] else ""
            st.markdown(
                f"""<div class="ffc-card">
                    <span class="ffc-song">{stern}{song}</span>
                    <div class="ffc-bar"><div style="width:{breite}%;
                         background:{farbe}"></div></div>
                    <div class="ffc-meta">Reifegrad {grad_text(g)}{zeit}
                         {'· ' + hinweis if hinweis else ''}</div>
                </div>""",
                unsafe_allow_html=True,
            )
        st.caption(f"Gesamtspielzeit der Auswahl: {setlaenge(df, geplant)}")

# ---------------------------------------------------------------- Analyse
with tabs[1]:
    df, hist = songs(), history()
    if df.empty:
        st.warning("Keine Songliste vorhanden.")
    else:
        im_set = df[df["Status"] == "im Set"]
        bewertet = df["Reifegrad"].notna()
        a, b, c, d = st.columns(4)
        a.metric("Songs", len(df), f"{len(im_set)} im Set")
        a2 = df.loc[bewertet, "Reifegrad"]
        b.metric("Ø Reifegrad", f"{a2.mean():.1f}" if len(a2) else "–",
                 f"{int(bewertet.sum())} von {len(df)} bewertet")
        c.metric("Unter 4", int((df["Reifegrad"] < 4).sum()))
        d.metric("Setlänge", setlaenge(df, im_set["Songtitel"]))

        offen = df[~bewertet]
        if not offen.empty:
            st.markdown(
                f'<div class="ffc-banner"><b>{len(offen)} Songs sind noch nicht bewertet.</b> '
                "Bis das nachgeholt ist, sind Durchschnitt und gewichtete Auswahl nur "
                "eingeschränkt aussagekräftig.</div>",
                unsafe_allow_html=True,
            )
            with st.expander(f"Die {len(offen)} unbewerteten Songs"):
                st.dataframe(offen[["Songtitel", "Status", "Spielzeit"]],
                             use_container_width=True, hide_index=True)

        zu_klaeren = df[df["Status"] == "zu klaeren"]
        if not zu_klaeren.empty:
            with st.expander(f"{len(zu_klaeren)} Songs mit ungeklärtem Status"):
                st.caption("Songtext vorhanden, aber unklar, ob gelernt, Kandidat oder Altlast.")
                st.dataframe(zu_klaeren[["Songtitel", "Interpret"]],
                             use_container_width=True, hide_index=True)

        if hist.empty:
            st.info("Noch keine Spielhistorie.")
        else:
            proben = hist["Gespielt_am"].dt.date.nunique()
            e, f = st.columns(2)
            e.metric("Proben erfasst", proben)
            f.metric("Ø Songs je Probe", f"{len(hist)/proben:.1f}" if proben else "–")

            plt.style.use("dark_background")
            g1, g2 = st.columns(2)
            with g1:
                st.markdown("### Meistgespielt")
                top = hist["Songtitel"].value_counts().head(10).iloc[::-1]
                grade = {k: (5 if pd.isna(v) else v)
                         for k, v in df.set_index("Songtitel")["Reifegrad"].items()}
                fig, ax = plt.subplots(figsize=(7, 5))
                for obj in (fig, ax):
                    obj.set_facecolor(T["ink"])
                ax.barh(top.index, top.values,
                        color=[color_for_reifegrad_mpl(grade.get(s, 5)) for s in top.index])
                ax.tick_params(colors=T["paper"])
                for s in ax.spines.values():
                    s.set_visible(False)
                plt.tight_layout()
                st.pyplot(fig)
            with g2:
                st.markdown("### Reifegrad-Verteilung")
                fig, ax = plt.subplots(figsize=(7, 5))
                for obj in (fig, ax):
                    obj.set_facecolor(T["ink"])
                ax.hist(df["Reifegrad"].dropna().astype(int), bins=range(0, 12),
                        color=T["red"], edgecolor=T["ink"])
                ax.set_xlabel("Reifegrad", color=T["paper"])
                ax.tick_params(colors=T["paper"])
                for s in ax.spines.values():
                    s.set_visible(False)
                plt.tight_layout()
                st.pyplot(fig)

        st.divider()
        st.markdown("### Datenqualität")
        abweichung = df[df["Anzahl_gespielt"] != df["Anzahl_laut_Historie"]]
        if abweichung.empty:
            st.success("Songliste und Spielhistorie stimmen überein.")
        else:
            st.warning(
                f"Bei {len(abweichung)} von {len(df)} Songs weicht die gepflegte Zählung "
                "von der Spielhistorie ab. Die Historie erfasst vermutlich erst einen "
                "Teil der Proben. Solange das ungeklärt ist, ist die Spalte "
                "'Anzahl gespielt' keine belastbare Kennzahl."
            )
            st.dataframe(
                abweichung[["Songtitel", "Anzahl_gespielt", "Anzahl_laut_Historie"]]
                .rename(columns={"Anzahl_gespielt": "in der Songliste",
                                 "Anzahl_laut_Historie": "laut Historie"}),
                use_container_width=True, hide_index=True,
            )

        if EDIT_MODE:
            try:
                roh = pd.read_csv(APP_CONFIG["files"]["history"], sep=";", encoding="utf-8-sig")
                ueberzaehlig = len(roh) - len(hist)
            except Exception:
                ueberzaehlig = 0
            if ueberzaehlig > 0:
                st.warning(
                    f"Die Datei `spielhistorie.csv` enthält {ueberzaehlig} überzählige Zeilen: "
                    "derselbe Song mehrfach für denselben Probentag. Die App rechnet bereits "
                    "ohne sie, die Datei ist aber noch unsauber."
                )
                if st.button("Spielhistorie bereinigen", use_container_width=True):
                    vorher, nachher = DataManager.bereinige_history()
                    frisch()
                    st.success(f"{vorher} Zeilen auf {nachher} reduziert.")
                    st.rerun()

        st.divider()
        x, y = st.columns(2)
        x.download_button("Songliste als CSV",
                          df.to_csv(index=False, sep=";").encode("utf-8-sig"),
                          "songliste_export.csv", "text/csv", use_container_width=True)
        if not hist.empty:
            y.download_button("Historie als CSV",
                              hist.to_csv(index=False, sep=";").encode("utf-8-sig"),
                              "spielhistorie_export.csv", "text/csv", use_container_width=True)

# ---------------------------------------------------------------- History
with tabs[2]:
    hist = history()
    if hist.empty:
        st.info("Noch keine Einträge.")
    else:
        jahre = sorted(hist["Gespielt_am"].dt.year.unique().astype(int), reverse=True)
        jahr = st.selectbox("Jahr", ["Alle"] + [str(j) for j in jahre])
        gefiltert = hist if jahr == "Alle" else hist[hist["Gespielt_am"].dt.year == int(jahr)]
        st.dataframe(
            gefiltert.sort_values("Gespielt_am", ascending=False),
            use_container_width=True, hide_index=True,
            column_config={"Gespielt_am": st.column_config.DateColumn("Datum", format="DD.MM.YYYY")},
        )

# ================================================================ Bearbeitung
if EDIT_MODE:
    # ------------------------------------------------------------ Auswahl
    with tabs[3]:
        df = songs()
        if df.empty:
            st.error("Songliste ist leer.")
        else:
            f1, f2 = st.columns(2)
            stati = sorted(df["Status"].unique())
            gewaehlte_stati = f1.multiselect("Status", stati, default=["im Set"] if "im Set" in stati else stati)
            alle_tags = sorted({t.strip() for s in df["Tags"] for t in str(s).split(",") if t.strip()})
            gewaehlte_tags = f2.multiselect("Nach Tags filtern", alle_tags)
            basis = df[df["Status"].isin(gewaehlte_stati)] if gewaehlte_stati else df
            if gewaehlte_tags:
                basis = basis[basis["Tags"].apply(
                    lambda x: any(t in [i.strip() for i in str(x).split(",")] for t in gewaehlte_tags))]

            s1, s2 = st.columns(2)
            anzahl = s1.slider("Anzahl Songs", 3, max(3, min(15, len(basis))), min(5, len(basis)))
            datum = s2.date_input("Datum der Probe", value=datetime.today())

            with st.expander("Gewichtung"):
                # Vorher waren diese beiden Regler vertauscht: der Must-Play-Regler
                # wirkte auf den Reifegrad und umgekehrt.
                w_reifegrad = st.slider(
                    "Gewicht: niedriger Reifegrad", 0.5, 3.0, 1.0, 0.1,
                    help="Je höher, desto stärker werden schlecht sitzende Songs bevorzugt.")
                w_mustplay = st.slider(
                    "Gewicht: Must-Play", 0.0, 5.0, 2.0, 0.5,
                    help="Je höher, desto stärker werden als Must-Play markierte Songs bevorzugt.")
                w_pause = st.slider(
                    "Gewicht: lange nicht gespielt", 0.0, 5.0, 2.0, 0.5)

            if st.button("Songs auswählen", use_container_width=True):
                tage = (pd.Timestamp.today().normalize() - basis["Zuletzt_gespielt"]).dt.days
                tage_norm = tage / max(tage.max(), 1)
                grad = basis["Reifegrad"].fillna(5).astype(int)
                gewicht = (
                    (10 - grad) * w_reifegrad
                    + basis["Must_Play"].astype(int) * w_mustplay
                    + tage_norm * w_pause
                ).clip(lower=0.1)
                st.session_state.auswahl = (
                    basis.sample(n=min(anzahl, len(basis)), weights=gewicht,
                                 random_state=random.randint(0, 10_000))["Songtitel"].tolist()
                )

            auswahl = st.session_state.get("auswahl", [])
            if auswahl:
                st.markdown("### Auswahl")
                for song in auswahl:
                    z = df[df["Songtitel"] == song].iloc[0]
                    g = z["Reifegrad"]
                    st.markdown(
                        f"""<div class="ffc-card">
                            <span class="ffc-song">{'★ ' if z['Must_Play'] else ''}{song}</span>
                            <div class="ffc-bar"><div style="width:{0 if pd.isna(g) else int(g)*10}%;
                                 background:{'rgba(231,222,209,.25)' if pd.isna(g) else color_for_reifegrad(g)}"></div></div>
                            <div class="ffc-meta">Reifegrad {grad_text(g)} ·
                                 zuletzt {z['Zuletzt_gespielt'].strftime('%d.%m.%Y')}</div>
                        </div>""", unsafe_allow_html=True)
                st.caption(f"Gesamtspielzeit: {setlaenge(df, auswahl)}")

                rest = sorted(set(df["Songtitel"]) - set(auswahl))
                if rest:
                    e1, e2 = st.columns([3, 1])
                    zusatz = e1.selectbox("Song ergänzen", rest)
                    if e2.button("Hinzufügen", use_container_width=True):
                        if zusatz not in st.session_state.auswahl:
                            st.session_state.auswahl.append(zusatz)
                        st.rerun()

                if st.button("Auswahl für die nächste Probe speichern", use_container_width=True):
                    if DataManager.speichere_naechste_probe(auswahl):
                        st.success("Gespeichert. Nicht vergessen: CSVs committen.")

                if st.button("Als gespielt eintragen", use_container_width=True):
                    if DataManager.ergaenze_history(auswahl, datum):
                        aktuell = DataManager.lade_songliste()
                        maske = aktuell["Songtitel"].isin(auswahl)
                        aktuell.loc[maske, "Anzahl_gespielt"] += 1
                        aktuell.loc[maske, "Zuletzt_gespielt"] = pd.to_datetime(datum)
                        DataManager.speichere_songliste(aktuell)
                        frisch()
                        st.success("In der Historie vermerkt.")
                        st.rerun()

    # ------------------------------------------------------------ Nachbereitung
    with tabs[4]:
        hist, df = history(), songs()
        if hist.empty:
            st.info("Noch keine Proben erfasst.")
        else:
            termine = sorted(hist["Gespielt_am"].dt.date.unique(), reverse=True)
            termin = st.selectbox("Probedatum", termine,
                                  format_func=lambda d: d.strftime("%d.%m.%Y"))
            gespielt = list(dict.fromkeys(
                hist[hist["Gespielt_am"].dt.date == termin]["Songtitel"].tolist()))
            st.caption(f"{len(gespielt)} Songs an diesem Termin")

            neue = {}
            for nr, song in enumerate(gespielt):
                z = df[df["Songtitel"] == song]
                roh = z.iloc[0]["Reifegrad"] if not z.empty else pd.NA
                akt = 5 if pd.isna(roh) else int(roh)
                kom = str(z.iloc[0]["Kommentar"]) if not z.empty else ""
                with st.expander(song, expanded=False):
                    c1, c2 = st.columns([1, 2])
                    neue[song] = (
                        c1.slider("Reifegrad", 0, 10, akt, key=f"r_{termin}_{nr}"),
                        c2.text_input("Kommentar", value=kom, key=f"k_{termin}_{nr}"),
                    )

            if neue and st.button("Änderungen speichern", use_container_width=True):
                aktuell = DataManager.lade_songliste()
                for song, (grad, kommentar) in neue.items():
                    idx = aktuell[aktuell["Songtitel"] == song].index
                    aktuell.loc[idx, "Reifegrad"] = grad
                    aktuell.loc[idx, "Kommentar"] = kommentar
                if DataManager.speichere_songliste(aktuell):
                    frisch()
                    st.success("Gespeichert.")
                    st.rerun()

    # ------------------------------------------------------------ Songliste
    with tabs[5]:
        if st.button("Backup erstellen"):
            st.success(f"Backup: {os.path.basename(backup_dateien())}")

        bearbeitet = st.data_editor(
            songs(), num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "Songtitel": st.column_config.TextColumn("Songtitel", required=True),
                "Zuletzt_gespielt": st.column_config.DateColumn("Zuletzt gespielt", format="DD.MM.YYYY"),
                "Interpret": st.column_config.TextColumn("Interpret"),
                "Status": st.column_config.SelectboxColumn(
                    "Status", options=["im Set", "in Arbeit", "Kandidat", "nicht im Repertoire", "zu klaeren"]),
                "Spielzeit": st.column_config.TextColumn("Spielzeit", help="mm:ss"),
                "Reifegrad": st.column_config.NumberColumn(
                    "Reifegrad", min_value=0, max_value=10, step=1, help="leer = noch nicht bewertet"),
                "Anzahl_gespielt": st.column_config.NumberColumn("Gespielt", min_value=0, step=1),
                "Must_Play": st.column_config.CheckboxColumn("Must-Play"),
                "Favorit": st.column_config.CheckboxColumn("Favorit"),
            },
            key="editor",
        )
        if st.button("Songliste speichern", use_container_width=True):
            sauber = bearbeitet[bearbeitet["Songtitel"].astype(str).str.strip() != ""]
            if DataManager.speichere_songliste(sauber):
                frisch()
                st.success("Gespeichert. Nicht vergessen: CSVs committen.")
                st.rerun()
