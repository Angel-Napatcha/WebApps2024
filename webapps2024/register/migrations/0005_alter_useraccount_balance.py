# Generated by Django 5.0.4 on 2024-04-21 20:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('register', '0004_useraccount_is_activated'),
    ]

    operations = [
        migrations.AlterField(
            model_name='useraccount',
            name='balance',
            field=models.DecimalField(decimal_places=2, max_digits=10),
        ),
    ]