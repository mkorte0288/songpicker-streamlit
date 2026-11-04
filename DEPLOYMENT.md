# Songpicker mit persönlichen Konten betreiben

Die Konto-App startet über `bandapp.wsgi:application`. Sie benutzt eine eigene
PostgreSQL-Datenbank. Die Streamlit-App bleibt separat. Bestehende CSV-Dateien
werden beim ersten Start der Konto-App nicht importiert. Neue Bands starten leer.

## Lokal starten

```sh
python -m pip install -r requirements-app.txt
export SONGPICKER_DEV=1
python manage.py migrate
python manage.py runserver
```

Öffne http://localhost:8000. Lokal schreibt die App Bestätigungslinks,
Einladungen und Passwort-Reset-Links ins Terminal. Im Cloud-Betrieb muss
`SONGPICKER_DEV` fehlen und die App verschickt diese Links per SMTP.

## Hosting

Ein Python-Webservice mit PostgreSQL und HTTPS genügt. Bei Render einen
Python-Webservice und eine Datenbank in derselben Region anlegen. Für SMTP
über Port 587 braucht der Webservice einen kostenpflichtigen Tarif.
Für den Webservice den Branch mit der Konto-App auswählen.

| Einstellung | Wert |
| --- | --- |
| Build | `pip install -r requirements-app.txt && python manage.py collectstatic --noinput` |
| Pre-Deploy | `python manage.py migrate --noinput` |
| Start | `gunicorn bandapp.wsgi:application --bind 0.0.0.0:$PORT --workers 2` |
| Laufzeit | Python 3.12 |

Umgebungsvariablen im Hosting-Dashboard hinterlegen.

- `DJANGO_SECRET_KEY` mit einem zufällig erzeugten, stabilen Schlüssel.
- `SONGPICKER_PUBLIC_URL` mit der tatsächlichen HTTPS-Adresse, ohne Pfad.
- `DJANGO_ALLOWED_HOSTS` mit dem Hostnamen der App, ohne Schema.
- `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` und bei Bedarf `PGPORT`
  mit den PostgreSQL-Verbindungsdaten. TLS ist standardmäßig erforderlich.
- `SMTP_HOST`, `SMTP_PORT` (standardmäßig 587), `SMTP_USER`, `SMTP_PASSWORD`
  und `SMTP_FROM` mit den Daten eines separaten Versandpostfachs.
  Für webgo das im Kundenportal ausgewiesene SMTP-Ziel mit STARTTLS verwenden.
- `TRUST_HTTPS_PROXY=1` ausschließlich hinter einem kontrollierten Proxy,
  der `X-Forwarded-Proto` zuverlässig setzt und Clientwerte überschreibt.

Zugangsdaten gehören in die Einstellungen des Hostings. Für einen eigenen
Hostnamen zuerst die Anbieterdomain prüfen und dann bei Bedarf eine
Subdomain verbinden.

## Abnahme vor der Freigabe

1. Zwei Testkonten über tatsächlich zugestellte E-Mails bestätigen.
2. Eine Band mit Logo anlegen und das zweite Konto als Mitglied einladen.
3. Mitgliedschaft annehmen, Bearbeitungsrechte prüfen und wieder entziehen.
4. Eine zweite Band anlegen. Für beide Konten die jeweils fremde Band-URL
   und Logo-URL aufrufen. Der Zugriff muss verweigert werden.
5. Ein Passwort über die empfangene Reset-Mail ändern und neu anmelden.
6. Nach einem Neustart prüfen, ob Logo, Songliste, Planung und Historie
   weiter verfügbar sind. Datenbank-Backups für den Betrieb einrichten.

## Lokale Tests

```sh
SONGPICKER_DEV=1 python manage.py test bandapp
```
