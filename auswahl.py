"""Fachlogik für die gewichtete Songauswahl, unabhängig von Streamlit."""

import pandas as pd


def auswahl_gewichte(basis, probentag, w_reifegrad=1.0, w_mustplay=2.0, w_pause=2.0):
    """Positives Gewicht je Song; unbekannte Spieltermine gelten als lange Pause."""
    if basis.empty:
        return pd.Series(dtype="float64", index=basis.index)

    letzter_tag = pd.to_datetime(basis["Zuletzt_gespielt"], errors="coerce")
    gespielt = letzter_tag.notna() & (letzter_tag > pd.Timestamp("1900-01-01"))
    pause = (pd.Timestamp(probentag).normalize() - letzter_tag).dt.days.clip(lower=0)
    laengste_bekannte_pause = int(pause[gespielt].max()) if gespielt.any() else 0
    pause = pause.where(gespielt, max(laengste_bekannte_pause, 1) + 30)
    pause_normiert = pause / max(float(pause.max()), 1.0)

    reifegrad = pd.to_numeric(basis["Reifegrad"], errors="coerce").fillna(5).clip(0, 10)
    gewicht = (
        (10 - reifegrad) * w_reifegrad
        + basis["Must_Play"].astype(int) * w_mustplay
        + pause_normiert * w_pause
    )
    return gewicht.clip(lower=0.1)
