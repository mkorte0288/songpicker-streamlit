from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("bandapp", "0003_membership_one_band_admin")]

    operations = [
        migrations.AlterField(
            model_name="plan", name="band",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="bandapp.band"),
        ),
        migrations.AddField(
            model_name="plan", name="completed", field=models.BooleanField(default=False),
        ),
        migrations.AlterModelOptions(name="plan", options={"ordering": ["day"]}),
        migrations.AddConstraint(
            model_name="plan",
            constraint=models.UniqueConstraint(fields=("band", "day"), name="unique_band_plan_day"),
        ),
    ]
