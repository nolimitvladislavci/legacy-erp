"""AI analiza + audio recording + integrity hash za KnjigaPrigovora."""
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('pos', '0040_receipt_member_fields')]
    operations = [
        migrations.AddField(model_name='knjigaprigovora', name='audio_recording',
            field=models.FileField(blank=True, null=True, upload_to='prigovori/audio/%Y/%m/', verbose_name='Zvučni zapis')),
        migrations.AddField(model_name='knjigaprigovora', name='ai_category',
            field=models.CharField(blank=True, max_length=30, verbose_name='AI kategorija')),
        migrations.AddField(model_name='knjigaprigovora', name='ai_sentiment',
            field=models.CharField(blank=True, max_length=15, verbose_name='AI sentiment')),
        migrations.AddField(model_name='knjigaprigovora', name='ai_priority',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='AI prioritet (1-5)')),
        migrations.AddField(model_name='knjigaprigovora', name='ai_suggested_response',
            field=models.TextField(blank=True, verbose_name='AI prijedlog odgovora')),
        migrations.AddField(model_name='knjigaprigovora', name='ai_analyzed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='AI analizirano')),
        migrations.AddField(model_name='knjigaprigovora', name='integrity_hash',
            field=models.CharField(blank=True, max_length=64, verbose_name='Integritetski hash')),
    ]
