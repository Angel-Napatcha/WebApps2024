# Generated by Django 5.0.4 on 2024-04-25 09:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payapp', '0006_alter_transaction_amount_sent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='amount_sent',
            field=models.DecimalField(decimal_places=2, max_digits=10, null=True),
        ),
    ]
