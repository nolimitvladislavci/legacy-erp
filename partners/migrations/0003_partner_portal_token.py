import uuid
from django.db import migrations, models


def gen_uuids(apps, schema_editor):
    Partner = apps.get_model('partners', 'Partner')
    for p in Partner.objects.all():
        p.portal_token = uuid.uuid4()
        p.save(update_fields=['portal_token'])


class Migration(migrations.Migration):
    dependencies = [
        ('partners', '0002_partner_contact_email_partner_contact_person_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='portal_token',
            field=models.UUIDField(default=uuid.uuid4, null=True),
        ),
        migrations.RunPython(gen_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='partner',
            name='portal_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
