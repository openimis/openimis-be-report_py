# Generated by Django 3.2.16 on 2023-01-26 09:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('report', '0003_update_permissions'),
    ]

    operations = [
        migrations.CreateModel(
            name='GeneratedReports',
            fields=[
                ('id', models.AutoField(db_column='ReportingId', primary_key=True, serialize=False)),
                ('reporting_date', models.TextField(db_column='ReportingDate')),
                ('start_date', models.DateField(db_column='StartDate')),
                ('end_date', models.DateField(db_column='EndDate')),
                ('record_found', models.IntegerField(db_column='RecordFound')),
                ('report_type', models.IntegerField(blank=True, db_column='ReportType', null=True)),
                ('commission_rate', models.DecimalField(blank=True, db_column='CommissionRate', decimal_places=2, max_digits=18, null=True)),
                ('report_mode', models.IntegerField(blank=True, db_column='ReportMode', default=0, null=True)),
                ('scope', models.IntegerField(blank=True, db_column='Scope', null=True)),
            ],
            options={
                'db_table': 'tblReporting',
                'managed': False,
            },
        ),
    ]
