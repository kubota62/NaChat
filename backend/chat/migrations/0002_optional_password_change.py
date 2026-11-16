from django.db import migrations, models


def clear_requirement(apps, schema_editor):
    apps.get_model('chat', 'User').objects.all().update(must_change_password=False)


class Migration(migrations.Migration):
    dependencies = [('chat', '0001_initial')]
    operations = [
        migrations.AlterField(model_name='user', name='must_change_password', field=models.BooleanField(default=False)),
        migrations.RunPython(clear_requirement, migrations.RunPython.noop),
    ]
