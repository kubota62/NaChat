from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('chat', '0002_optional_password_change')]
    operations = [migrations.AddField(model_name='audit', name='details', field=models.JSONField(default=dict, blank=True))]
