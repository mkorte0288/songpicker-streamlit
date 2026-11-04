# Songpicker betreiben und freigeben

Diese Anleitung gilt für die Konto-App. Die separate Streamlit-App verwendet
weiterhin ihre bisherigen Daten. Die Konto-App startet mit leeren Bands.

## Lokal prüfen

```sh
python -m pip install -r requirements-app.txt
SONGPICKER_DEV=1 python manage.py test bandapp
SONGPICKER_DEV=1 python manage.py migrate
SONGPICKER_DEV=1 python manage.py runserver
```

Lokal ist die App unter http://localhost:8000 erreichbar. Nachrichten werden
ins Terminal geschrieben. Für Tests gegen PostgreSQL kann im Entwicklungsmodus
zusätzlich eine separate, zum Testen bestimmte `DATABASE_URL` gesetzt werden.
Django legt für seine Tests eine eigene Testdatenbank an.

## Kleiner Start ohne laufende Hostingkosten

Die Render-Vorlage `render.yaml` definiert einen kostenlosen Python-Webservice
in Frankfurt. Als Datenbank ist ein separates PostgreSQL in einer EU-Region
vorgesehen, etwa Neon Free. Der kostenlose Render-Datenbanktarif läuft nach
30 Tagen ab und ist daher für diese Umgebung ungeeignet. Der kostenlose
Webservice kann nach Leerlauf schlafen und beim ersten Aufruf verzögert reagieren.

Für Registrierung, Einladungen und Reset kann Brevo per HTTPS senden. Ein
verifizierter Absender und die vom Anbieter ausgegebenen DNS-Einträge sind
Voraussetzung. Die App unterstützt alternativ SMTP, wenn der Host ausgehenden
SMTP-Verkehr zum gewählten Dienst erlaubt. Render Free blockiert 25, 465 und 587.
CleverReach stellt transaktionale E-Mails nach eigener Dokumentation als
separates SMTP-Angebot bereit. Das Newsletter-Freikontingent ist dafür keine
gesicherte laufende Preisgrundlage.

### Im Dashboard eintragen

1. Das Repository in Render verbinden und die Vorlage auf dem freigegebenen
   Stand auswählen. Vor Bestätigung prüfen, dass
   nur der kostenlose Webservice provisioniert wird.
2. Bei Neon ein separates PostgreSQL-Projekt in einer EU-Region anlegen.
   Die Verbindungs-URL als `DATABASE_URL` in Render setzen. TLS ist
   standardmäßig erforderlich. Für die Abnahme getrennte Testdaten verwenden.
3. Den Absender beim Maildienst verifizieren. Für Brevo einen API-Schlüssel
   erstellen und als `BREVO_API_KEY` hinterlegen. `SMTP_FROM` enthält die
   verifizierte Absenderadresse. Für SMTP stattdessen `SMTP_HOST`,
   `SMTP_PORT`, `SMTP_USER` und `SMTP_PASSWORD` setzen.
4. `DJANGO_ALLOWED_HOSTS` auf den exakten Hostnamen der App setzen und
   `SONGPICKER_PUBLIC_URL` auf deren HTTPS-URL ohne Pfad. Der Blueprint
   erzeugt `DJANGO_SECRET_KEY`. Zugangsdaten bleiben im Dashboard.
5. `TRUST_HTTPS_PROXY=1` setzt voraus, dass der kontrollierte Eingangsproxy
   das HTTPS-Schema zuverlässig setzt und Clientwerte überschreibt.
   `SONGPICKER_TRUSTED_PROXY_HOPS` erst setzen, nachdem die tatsächliche
   X-Forwarded-For-Kette mit zwei unabhängigen Netzwerken und einem
   absichtlich gefälschten Prefix überprüft wurde. Der Wert beschreibt
   die Anzahl der vom vertrauenswürdigen Eingangsweg angehängten Adressen,
   einschließlich der Client-Adresse. Bei 0 verwendet die App REMOTE_ADDR.

### Registrierung und echte Abnahme

Die öffentliche Registrierung ist standardmäßig geschlossen. Setze für die
Abnahme nur eigene Test-E-Mail-Adressen in `SONGPICKER_PREFLIGHT_EMAILS`
(kommagetrennt). Aktiviere `SONGPICKER_PUBLIC_SIGNUP=1` erst nach erfolgreicher
Abnahme. Die App verlangt dafür auch `SONGPICKER_LEGAL_NOTICE_URL` und
`SONGPICKER_PRIVACY_NOTICE_URL` mit veröffentlichten HTTPS-Links.
Die Betreiberinformationen und die tatsächlichen Anbieter vor der Freigabe
prüfen und die Auftragsverarbeitung dokumentieren.

1. HTTPS und `/healthz/` aufrufen. Mit zwei eigenen Adressen registrieren und
   die empfangenen Bestätigungslinks öffnen. Auch Absender und Spamordner prüfen.
2. Eine fiktive Band mit Logo anlegen. Ein zweites Konto einladen. Einladung
   annehmen, Zugriff nach Rollen prüfen und Passwort-Reset durchführen.
3. Eine zweite Band anlegen. Mit beiden Konten die jeweils fremde Band-URL
   und Logo-URL prüfen. Beide fremden Zugriffe müssen abgewiesen werden.
4. Admin übertragen. Ein Mitglied verlässt die Band und löscht sein Konto.
   Eine eigens für den Test angelegte Band löschen. Prüfen, ob nur die
   vorgesehenen Daten entfernt wurden.
5. Missbrauchsschutz von zwei Netzwerken prüfen. Eine Rate-Limit-Sperre
   darf das zweite Netzwerk nicht treffen. Ein clientseitig gesendeter
   Forwarding-Prefix darf die Sperre nicht umgehen.
6. Einen PostgreSQL-Export erzeugen, verschlüsselt aufbewahren und in einer
   leeren Wiederherstellungsdatenbank einspielen. Dann Anzahl der Bands,
   Testkonten, Proben und die Logo-Daten prüfen. Wiederherstellung niemals
   auf der aktiven Datenbank ausprobieren. Regelmäßige Sicherungen und eine
   Löschfrist für Sicherungen festlegen. Den Ablauf und das Ergebnis datieren.
7. Nach einem Neustart prüfen, dass Logo, Songliste, Planung und Historie
   erhalten bleiben. Erst danach Foo Fightclub einladen und das Datum festhalten.

### Foo Fightclub: alte Daten übernehmen

Nach der technischen Abnahme legt der Admin eine **leere** Band an und öffnet
„Songs → Alte Songpicker-Daten übernehmen“. Dort lädt er `songliste.csv` und
`spielhistorie.csv` aus dem bisherigen Songpicker hoch. Die Übernahme ist nur
einmal und nur in eine leere Band möglich. Vorher eine Sicherung der beiden
Dateien anlegen. Anschließend Anzahl und Stichproben von Titeln, Status,
Spielzeit, Reifegrad, Must-Play, Favoriten, Tags, Kommentaren, Notizen und
Historie prüfen.

Gleiche Songtitel an demselben Probentag werden in der Historie zusammengefasst.
Der alte Gesamtzähler bleibt als Kombination aus datierten Historieneinträgen
und einem undatierten Altbestand erhalten. Falls die Historie mehr Einträge als
der alte Zähler enthält, zeigt die App die Abweichung beim Import an und
verwendet die belegten Historieneinträge. Die alte Datei
`naechste_probe.csv` enthält kein Datum; diese Probe muss mit einem Datum neu
geplant werden. Die alte Streamlit-App bleibt bis zur fachlichen Prüfung die
Referenz. Öffentliche Registrierung erst nach dieser Abnahme freigeben.
