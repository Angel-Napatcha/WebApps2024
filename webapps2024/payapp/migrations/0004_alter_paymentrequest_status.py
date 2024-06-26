# Generated by Django 5.0.4 on 2024-04-24 16:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payapp', '0003_paymentrequest_amount_in_recipient_currency'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentrequest',
            name='status',
            field=models.CharField(choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')], default='Pending', max_length=15),
        ),
    ]
