from django.db import migrations, models


class Migration(migrations.Migration):
    """
    0031 — TSE polja na POSReceipt za KassenSichV (DE fiskalizacija).

    Novi modeli/polja:
      POSReceipt:
        tse_transaction_number  — Fiskaly/TSE broj transakcije
        tse_signature_counter   — Signaturzähler (mora biti na računu)
        tse_hash                — Kriptografski potpis (base64)
        tse_serial_number       — Serijski broj TSE modula
        tse_start_time          — Početak TSE transakcije
        tse_end_time            — Kraj TSE transakcije
        tse_error               — Zadnja greška (ako TSE padne, naplata ide dalje)
    """
    dependencies = [
        ("pos", "0030_order_source_field"),
    ]

    operations = [
        # TSE polja na POSReceipt
        migrations.AddField(
            model_name="posreceipt",
            name="tse_transaction_number",
            field=models.CharField(
                max_length=50,
                null=True,
                blank=True,
                verbose_name="TSE Transaktionsnummer",
                help_text="Fiskaly/TSE jedinstveni broj transakcije",
            ),
        ),
        migrations.AddField(
            model_name="posreceipt",
            name="tse_signature_counter",
            field=models.PositiveIntegerField(
                null=True,
                blank=True,
                verbose_name="TSE Signaturzähler",
                help_text="KassenSichV §10: mora biti ispisan na računu",
            ),
        ),
        migrations.AddField(
            model_name="posreceipt",
            name="tse_hash",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="TSE Signaturwert (hash)",
                help_text="Kriptografski potpis transakcije — za QR kod na računu",
            ),
        ),
        migrations.AddField(
            model_name="posreceipt",
            name="tse_serial_number",
            field=models.CharField(
                max_length=100,
                blank=True,
                default="",
                verbose_name="TSE Seriennummer",
                help_text="Serijski broj TSE modula koji je potpisao transakciju",
            ),
        ),
        migrations.AddField(
            model_name="posreceipt",
            name="tse_start_time",
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name="TSE Zeitpunkt Start",
            ),
        ),
        migrations.AddField(
            model_name="posreceipt",
            name="tse_end_time",
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name="TSE Zeitpunkt Ende",
            ),
        ),
        migrations.AddField(
            model_name="posreceipt",
            name="tse_error",
            field=models.CharField(
                max_length=200,
                blank=True,
                default="",
                verbose_name="TSE greška",
                help_text="Zadnja TSE greška — prazno = OK",
            ),
        ),
    ]

