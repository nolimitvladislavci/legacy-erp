from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0008_bookingservice_requires_actor_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='actor_resource',
            field=models.ForeignKey(
                to='appointments.BookingResource',
                on_delete=django.db.models.deletion.SET_NULL,
                null=True, blank=True,
                related_name='actor_appointments',
                verbose_name='Dodijeljeni izvrsitelj (resurs)',
                help_text='BookingResource tipa ljudstvo dodijeljen ovom terminu. '
                          'Koristi se za Actor Shortage provjeru u scheduling engineu.',
            ),
        ),
    ]
