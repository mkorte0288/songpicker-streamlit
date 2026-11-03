import os
import tempfile
import unittest
import zipfile
from io import BytesIO
from unittest.mock import patch

from config import APP_CONFIG
from data_manager import DataManager
from utils import backup_als_zip


class TestDataManager(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.files = {
            "songs": os.path.join(self.temp.name, "songliste.csv"),
            "history": os.path.join(self.temp.name, "spielhistorie.csv"),
            "naechste_probe": os.path.join(self.temp.name, "naechste_probe.csv"),
            "backup_dir": os.path.join(self.temp.name, "backups"),
        }
        patched = patch.dict(APP_CONFIG["files"], self.files)
        patched.start()
        self.addCleanup(patched.stop)

    def test_no_github_in_cloud_does_not_write(self):
        with patch("data_manager.EDIT_ENV", False), \
             patch("data_manager.github_speicher.verfuegbar", return_value=False), \
             patch("data_manager.st.error"):
            self.assertFalse(DataManager.speichere_naechste_probe(["Everlong"]))
        self.assertFalse(os.path.exists(self.files["naechste_probe"]))

    def test_github_failure_restores_existing_file(self):
        path = self.files["naechste_probe"]
        with open(path, "w", encoding="utf-8") as f:
            f.write("Old Song\n")
        with patch("data_manager.EDIT_ENV", False), \
             patch("data_manager.github_speicher.verfuegbar", return_value=True), \
             patch("data_manager.github_speicher.speichere", return_value=(False, "409 conflict")), \
             patch("data_manager.st.error"):
            self.assertFalse(DataManager.speichere_naechste_probe(["New Song"]))
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "Old Song\n")

    def test_github_failure_removes_new_file(self):
        with patch("data_manager.EDIT_ENV", False), \
             patch("data_manager.github_speicher.verfuegbar", return_value=True), \
             patch("data_manager.github_speicher.speichere", return_value=(False, "network")), \
             patch("data_manager.st.error"):
            self.assertFalse(DataManager.speichere_naechste_probe(["New Song"]))
        self.assertFalse(os.path.exists(self.files["naechste_probe"]))

    def test_local_editing_without_github_is_allowed(self):
        with patch("data_manager.EDIT_ENV", True), \
             patch("data_manager.github_speicher.verfuegbar", return_value=False):
            self.assertTrue(DataManager.speichere_naechste_probe(["Everlong"]))
        with open(self.files["naechste_probe"], encoding="utf-8") as f:
            self.assertEqual(f.read(), "Everlong\n")

    def test_duplicate_recording_does_not_add_another_occurrence(self):
        with open(self.files["history"], "w", encoding="utf-8") as f:
            f.write("Songtitel;Gespielt_am\nEverlong;2026-11-04\n")
        with patch.object(DataManager, "speichere_history") as save:
            self.assertEqual(DataManager.ergaenze_history(["Everlong"], "2026-11-04"), (True, []))
            save.assert_not_called()

    def test_new_recording_is_added_only_once(self):
        with open(self.files["history"], "w", encoding="utf-8") as f:
            f.write("Songtitel;Gespielt_am\nEverlong;2026-11-01\n")
        with patch.object(DataManager, "speichere_history", return_value=True) as save:
            ok, songs = DataManager.ergaenze_history(["Everlong", "Everlong", "Walk"], "2026-11-04")
            self.assertTrue(ok)
            self.assertEqual(songs, ["Everlong", "Walk"])
            self.assertEqual(len(save.call_args.args[0]), 3)

    def test_history_cleanup_reports_persistence_failure(self):
        with open(self.files["history"], "w", encoding="utf-8") as f:
            f.write("Songtitel;Gespielt_am\nEverlong;2026-11-04\nEverlong;2026-11-04\n")
        with patch.object(DataManager, "speichere_history", return_value=False):
            self.assertEqual(DataManager.bereinige_history(), (2, 1, False))

    def test_downloadable_backup_contains_all_three_files(self):
        for key in ("songs", "history", "naechste_probe"):
            with open(self.files[key], "w", encoding="utf-8") as f:
                f.write(key)
        with zipfile.ZipFile(BytesIO(backup_als_zip())) as backup:
            self.assertEqual(len(backup.namelist()), 3)
            self.assertEqual(backup.read("songliste.csv"), b"songs")


if __name__ == "__main__":
    unittest.main()
