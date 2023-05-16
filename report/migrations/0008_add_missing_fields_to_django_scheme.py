# Generated by Django 3.2.18 on 2023-05-16 09:32

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0013_auto_20230317_1534'),
        ('product', '0008_auto_20230510_1347'),
        ('payer', '0001_initial'),
        ('core', '0019_extended_field'),
        ('report', '0007_add_edit_perms_imis_and_scheme_admin'),
    ]

    operations = [
        migrations.AddField(
            model_name='generatedreports',
            name='location',
            field=models.ForeignKey(db_column='LocationId', on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='location.location'),
        ),
        migrations.AddField(
            model_name='generatedreports',
            name='officer',
            field=models.ForeignKey(blank=True, db_column='OfficerID', null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='core.officer'),
        ),
        migrations.AddField(
            model_name='generatedreports',
            name='payer',
            field=models.ForeignKey(blank=True, db_column='PayerId', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='generated_reports', to='payer.payer'),
        ),
        migrations.AddField(
            model_name='generatedreports',
            name='product',
            field=models.ForeignKey(db_column='ProdId', on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='product.product'),
        ),
    ]