import unittest

import pandas as pd

from auswahl import auswahl_gewichte


def songliste(letzte=None, reifegrade=None, must_play=None):
    return pd.DataFrame({
        "Songtitel": ["A", "B"],
        "Zuletzt_gespielt": letzte or [pd.Timestamp("1900-01-01"), pd.Timestamp("2026-11-01")],
        "Reifegrad": reifegrade or [5, 5],
        "Must_Play": must_play or [False, False],
    })


class TestAuswahl(unittest.TestCase):
    def test_empty_selection_is_supported(self):
        self.assertTrue(auswahl_gewichte(songliste().iloc[0:0], "2026-11-04").empty)

    def test_never_played_song_gets_priority_over_recent_song(self):
        gewichte = auswahl_gewichte(songliste(), "2026-11-04")
        self.assertGreater(gewichte.iloc[0], gewichte.iloc[1])

    def test_rehearsal_date_used_instead_of_current_day(self):
        basis = songliste(letzte=[pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-18")])
        gewichte = auswahl_gewichte(basis, "2026-10-20", w_reifegrad=0.5, w_pause=5.0)
        self.assertGreater(gewichte.iloc[0], gewichte.iloc[1])

    def test_low_maturity_gets_priority(self):
        basis = songliste(letzte=[pd.Timestamp("2026-11-01")] * 2, reifegrade=[2, 9])
        gewichte = auswahl_gewichte(basis, "2026-11-04", w_pause=0.0)
        self.assertGreater(gewichte.iloc[0], gewichte.iloc[1])

    def test_must_play_has_positive_effect(self):
        basis = songliste(letzte=[pd.Timestamp("2026-11-01")] * 2, must_play=[True, False])
        gewichte = auswahl_gewichte(basis, "2026-11-04")
        self.assertGreater(gewichte.iloc[0], gewichte.iloc[1])

    def test_missing_maturity_is_safe(self):
        basis = songliste(reifegrade=[pd.NA, 7])
        gewicht = auswahl_gewichte(basis, "2026-11-04")
        self.assertTrue((gewicht > 0).all())


if __name__ == "__main__":
    unittest.main()
