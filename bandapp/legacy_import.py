"""One-time import for the previous Foo Fightclub Streamlit CSV format."""

import csv
import re
import unicodedata
from collections import Counter
from datetime import date
from io import StringIO


STATUS = {
    "im Set": "set", "in Arbeit": "work", "Kandidat": "candidate",
    "zu klaeren": "unclear", "nicht im Repertoire": "out",
}


def _key(value):
    return unicodedata.normalize("NFC", value.strip()).casefold()


def _rows(upload, required):
    if upload.size > 2_000_000:
        raise ValueError("Die CSV-Datei darf höchstens 2 MB groß sein.")
    try:
        text = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Die CSV-Datei muss UTF-8-codiert sein.") from error
    reader = csv.DictReader(StringIO(text), delimiter=";")
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError("Die CSV-Spalten entsprechen nicht dem alten Songpicker-Format.")
    rows = list(reader)
    if any(any(row.get(field) is None for field in required) for row in rows):
        raise ValueError("Die CSV-Datei enthält eine unvollständige Zeile.")
    return rows


def _boolean(value):
    if value.lower() in {"true", "1"}:
        return True
    if value.lower() in {"false", "0", ""}:
        return False
    raise ValueError("Ein Ja/Nein-Wert in der Songliste ist ungültig.")


def _optional(row, key):
    return (row.get(key) or "").strip()


def parse_legacy(song_upload, history_upload):
    songs = _rows(song_upload, {"Songtitel", "Interpret", "Status", "Spielzeit", "Reifegrad", "Anzahl_gespielt", "Must_Play"})
    history = _rows(history_upload, {"Songtitel", "Gespielt_am"})
    if not songs or len(songs) > 500 or len(history) > 10000:
        raise ValueError("Erwartet werden 1 bis 500 Songs und höchstens 10.000 Historieneinträge.")
    by_key = {}
    prepared = []
    for row in songs:
        title = row["Songtitel"].strip()
        key = _key(title)
        if not title or len(title) > 160 or key in by_key:
            raise ValueError("Die Songliste enthält leere, zu lange oder doppelte Titel.")
        status = STATUS.get(row["Status"].strip())
        if status is None:
            raise ValueError(f"Unbekannter Songstatus bei {title}.")
        duration = row["Spielzeit"].strip()
        if duration and not re.fullmatch(r"[0-9]{1,8}:[0-5][0-9]", duration):
            raise ValueError(f"Ungültige Spielzeit bei {title}.")
        minutes, seconds = map(int, duration.split(":")) if duration else (0, 0)
        if minutes * 60 + seconds > 24 * 60 * 60:
            raise ValueError(f"Die Spielzeit bei {title} ist zu lang.")
        grade_text = row["Reifegrad"].strip()
        count_text = row["Anzahl_gespielt"].strip()
        try:
            grade = int(grade_text) if grade_text else None
            count = int(count_text)
        except ValueError as error:
            raise ValueError(f"Ungültiger Reifegrad oder Zähler bei {title}.") from error
        if (grade is not None and not 0 <= grade <= 10) or not 0 <= count <= 1_000_000:
            raise ValueError(f"Ungültiger Reifegrad oder Zähler bei {title}.")
        item = {
            "title": title, "artist": row["Interpret"].strip(), "status": status,
            "duration": minutes * 60 + seconds, "grade": grade,
            "must_play": _boolean(row["Must_Play"].strip()),
            "favorite": _boolean(_optional(row, "Favorit")),
            "tags": _optional(row, "Tags"), "comment": _optional(row, "Kommentar"),
            "note": _optional(row, "Notiz"), "declared_count": count,
        }
        if (len(item["artist"]) > 160 or len(item["tags"]) > 500
                or len(item["comment"]) > 1000 or len(item["note"]) > 1000):
            raise ValueError(f"Ein Feld bei {title} ist zu lang.")
        prepared.append(item)
        by_key[key] = item
    played = set()
    for row in history:
        key = _key(row["Songtitel"])
        if key not in by_key:
            raise ValueError(f"Historieneintrag ohne passenden Song: {row['Songtitel']}.")
        try:
            day = date.fromisoformat(row["Gespielt_am"].strip())
        except ValueError as error:
            raise ValueError("Die Historie enthält ein ungültiges Datum.") from error
        played.add((key, day))
    counts = Counter(key for key, _ in played)
    corrections = 0
    for item in prepared:
        historical = counts[_key(item["title"])]
        declared = item.pop("declared_count")
        item["legacy_play_count"] = max(0, declared - historical)
        if historical > declared:
            corrections += 1
    return prepared, played, len(history) - len(played), corrections
