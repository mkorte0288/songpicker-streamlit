# Foo Fightclub Songpicker

Streamlit-App zur Probenplanung mit Reifegrad, Must-Play-Markierungen,
Spielhistorie und gewichteter Songauswahl.

## Lokal starten

1. Python 3.11 verwenden; dann: pip install -r requirements.txt
2. Nur lesen: streamlit run songpicker_streamlit.py
3. Bearbeiten: SONGPICKER_EDIT=1 streamlit run songpicker_streamlit.py
4. Tests: python -m unittest discover -s tests -v

## Datenspeicherung

Songliste, Historie und Auswahl werden als CSV-Dateien gespeichert.
Lokal kann im expliziten Bearbeitungsmodus ohne GitHub gearbeitet werden.
In der gehosteten App werden für die dauerhafte Speicherung die
Streamlit-Secrets edit_password, github_token und github_repo benötigt.
github_branch ist optional (Standard: main).

Bei Fehlern während des GitHub-Commits wird ein Fehler angezeigt und die
zuvor vorhandene lokale Datei wiederhergestellt. Backups können im
Bearbeitungsmodus unter „Songliste“ als ZIP heruntergeladen werden.

Achtung: Der GitHub-basierte Speicher ist nur für die jetzige einzelne
Band gedacht und weder für viele parallele Nutzer noch für Mandanten
geeignet. Die CSVs liegen derzeit in einem öffentlichen Repository.

## Probenablauf

1. Status und Tags filtern, Anzahl und Datum wählen.
2. Gewichtete Auswahl erzeugen, Songs ergänzen oder entfernen und speichern.
3. Nach der Probe nur tatsächlich gespielte Songs markieren.
4. Die App erfasst neue Kombinationen aus Song und Datum genau einmal.
5. Unter „Nachbereitung“ Reifegrad und Kommentar aktualisieren.

Die Fachlogik der Auswahl liegt in auswahl.py und lässt sich separat testen.
Unbewertete Songs werden nur für die Gewichtung neutral (Reifegrad 5)
gerechnet, nicht dauerhaft auf 5 gesetzt.

## Datenqualität

118 doppelte Historienzeilen wurden in diesem Änderungsvorschlag aus
spielhistorie.csv entfernt. Historische Werte in Anzahl_gespielt können
trotzdem von der teilweise unvollständigen Historie abweichen und werden
bewusst nicht automatisch überschrieben. Änderungen am Songtitel können
aktuell die Zuordnung historischer Einträge auflösen; später sind stabile
Song-IDs erforderlich.

## Langfristiger Ausblick: Bandmanagement-Plattform

Derzeit ein Single-Band-Prototyp, noch kein SaaS. In einem separaten
Ausbauschritt wären sinnvoll:

- Datenbank mit stabilen IDs, Migration und transaktionaler Speicherung
- Benutzerkonten, Rollen und sichere Zugriffskontrolle
- Strikte Datentrennung zwischen Bands
- Gemeinsame Probenplanung, Setlisten, Auftritte und Verfügbarkeiten
- Monitoring, Datenschutzkonzept und Zahlungsabwicklung

Vor der kommerziellen Nutzung dürfen keine personenbezogenen Kundendaten
in öffentlich lesbare CSV-Dateien oder Repositories geschrieben werden.
