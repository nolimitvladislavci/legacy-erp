from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('superadmin_ai', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='aimodulepermission',
            name='can_read',
            field=models.BooleanField(default=False, verbose_name='Čitanje'),
        ),
        migrations.AddField(
            model_name='aimodulepermission',
            name='can_write',
            field=models.BooleanField(default=False, verbose_name='Pisanje'),
        ),
        migrations.AddField(
            model_name='aimodulepermission',
            name='can_create',
            field=models.BooleanField(default=False, verbose_name='Kreiranje'),
        ),
        migrations.AddField(
            model_name='aimodulepermission',
            name='can_modify',
            field=models.BooleanField(default=False, verbose_name='Izmjene'),
        ),
        migrations.AddField(
            model_name='pendingaiaction',
            name='proposed_code',
            field=models.TextField(blank=True, default='', verbose_name='Predloženi kod'),
        ),
        # Ukloni unique_together jer sync_local_modules radi bez company
        migrations.AlterUniqueTogether(
            name='aimodulepermission',
            unique_together={('company', 'module')},
        ),
    ]
