# Generated by Django 5.0.4 on 2024-04-18 08:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('register', '0003_useraccount_delete_usercurrency'),
    ]

    operations = [
        migrations.AddField(
            model_name='useraccount',
            name='is_activated',
            field=models.BooleanField(default=False),
        ),
    ]
