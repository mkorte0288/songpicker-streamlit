from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bandapp", "0004_plans_by_day")]

    operations = [
        migrations.AlterField(
            model_name="song", name="status",
            field=models.CharField(
                choices=[("set", "Im Set"), ("work", "In Arbeit"), ("candidate", "Kandidat"),
                         ("unclear", "Zu klären"), ("out", "Nicht im Repertoire")],
                default="set", max_length=20, verbose_name="Status",
            ),
        ),
        migrations.AddField(model_name="song", name="favorite", field=models.BooleanField(default=False, verbose_name="Favorit")),
        migrations.AddField(model_name="song", name="tags", field=models.CharField(blank=True, max_length=500, verbose_name="Tags")),
        migrations.AddField(model_name="song", name="note", field=models.TextField(blank=True, max_length=1000, verbose_name="Notiz")),
        migrations.AddField(model_name="song", name="legacy_play_count", field=models.PositiveIntegerField(default=0)),
    ]
