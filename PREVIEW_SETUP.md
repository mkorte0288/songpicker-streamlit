# Isolierte Songpicker-Testversion

Dieser Branch enthält ausschließlich **synthetische Probedaten**. Die produktiven
Banddaten liegen auf dem Branch main und bleiben unverändert.

## Neue App auf Streamlit Community Cloud erstellen

1. https://share.streamlit.io öffnen und mit dem verbundenen GitHub-Konto anmelden.
2. **Create app** > **Yup, I have an app**.
3. Repository: mkorte0288/songpicker-streamlit
4. Branch: preview/songpicker-validation-20261104
5. Main file path: songpicker_streamlit.py
6. Optionaler Appname: songpicker-ffc-preview (falls frei).
7. Unter **Advanced settings** Python 3.11 auswählen.
8. Im Feld **Secrets** die folgenden Werte eintragen, aber niemals den
   echten Token oder das Passwort in GitHub committen:

   edit_password = "<eigenes-starkes-testpasswort>"
   github_token = "<separater-feingranularer-GitHub-Token>"
   github_repo = "mkorte0288/songpicker-streamlit"
   github_branch = "preview/songpicker-validation-20261104"

9. Den GitHub-Token für dieses Repository mit Contents: Read and write anlegen.
   Verwende am besten einen eigenen kurzlebigen Test-Token. Den Token niemals
   im Chat teilen oder in Dateien ablegen.
10. Deploy wählen.

**Sicherheitsgrenze:** Der Preview-Code akzeptiert Speichern nur, wenn
github_repo und github_branch genau wie oben konfiguriert sind. Bei einer
anderen Branch-Konfiguration sind Cloud-Schreibzugriffe deaktiviert.

## Funktionstest (Testdaten sind fiktiv)

1. Leseansicht: geplante Songs und Analyse prüfen.
2. Seitenleiste öffnen, mit Testpasswort anmelden.
3. Unter „Auswahl“ nur zwei Songs filtern und auswählen.
4. Auswahl verändern (einen Song entfernen, einen weiteren ergänzen).
5. Auswahl speichern, Browser aktualisieren und gespeicherte Auswahl prüfen.
6. Unter „Tatsächlich gespielt“ einen Song abwählen und die Probe erfassen.
7. Den Vorgang wiederholen: Es dürfen keine doppelten Historieneinträge entstehen.
8. Unter „Nachbereitung“ Reifegrad und Kommentar ändern.
9. Unter „Songliste“ eine ZIP-Datei herunterladen und deren Inhalt prüfen.
10. Erneut aktualisieren und prüfen, ob Änderungen erhalten bleiben.

## Hinweise

- Die **Live-App wird nicht verändert**.
- Jeder Speichervorgang im Preview löst einen Commit auf dem Preview-Branch aus.
  Streamlit kann daraufhin neu deployen.
- Der Preview-Branch wird nach dem Test gelöscht oder wieder auf Beispieldaten
  zurückgesetzt.
- Die neue App entsteht erst, wenn du sie im eigenen Streamlit-Konto deployt hast.
- Der Pull Request #1 ist weiterhin nicht gemergt.
