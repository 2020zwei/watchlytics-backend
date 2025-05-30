# Generated by Django 4.2.7 on 2025-05-19 07:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0003_followup_customertag'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='customer',
            constraint=models.UniqueConstraint(condition=models.Q(('email__isnull', False)), fields=('user', 'email'), name='unique_user_customer_email'),
        ),
    ]
