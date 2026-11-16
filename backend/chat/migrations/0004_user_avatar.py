from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('chat', '0003_audit_details')]
    operations = [migrations.AddField(model_name='user', name='avatar', field=models.FileField(upload_to='avatars/', blank=True))]
