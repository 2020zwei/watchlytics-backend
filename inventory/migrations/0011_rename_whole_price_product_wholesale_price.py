# Generated by Django 4.2.7 on 2025-05-14 07:41

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0010_product_year'),
    ]

    operations = [
        migrations.RenameField(
            model_name='product',
            old_name='whole_price',
            new_name='wholesale_price',
        ),
    ]
