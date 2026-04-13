# GEMINI_TASK: Service AI Agent — Stolarija (Tjedan 3, nakon launcha)
# Kreirao: Sonnet — 2026-04-10
# Ovisi o: CC_TASK_STOLARIJA_V1.md mora biti deployed
# Model: Human-in-the-loop UVIJEK — autopilot tek nakon 100 verificiranih slučajeva

---

## ARHITEKTURA (Geminijev prijedlog, verificiran Sonnetom)

```
ServiceVisit.scheduled - 14 dana = TRIGGER
    ↓
Celery task: generate_service_reminder(warranty_id)
    ↓
Gemini Pro: personalizirani email tekst (ime, adresa, što je ugrađeno)
    ↓
FenixInboxItem(izvor='ai_draft', status='ceka_odobrenje')
    ↓
Zdenko vidi u dashboardu: "Predloženi email — klikni Odobri"
    ↓
Zdenko klikne ODOBRI → šalje se email
    ↓
Kupac odgovori → webhook → FenixInboxItem(izvor='email', status='novo')
    ↓
Gemini analizira odgovor (tekst + slika ako postoji)
    ↓
Sentiment check: negativan? → eskalacija Zdenku, STOP AI
Slika: confidence < 70%? → AI traži bolju sliku
OK? → AI predlaže 3 termina iz kalendara
    ↓
Zdenko ODOBRI termin → ServiceVisit kreira se u bazi
    ↓
BookingSignature.log(action='service_scheduled', ai_validated=True)
```

---

## MODELI koji trebaju update

### ServiceVisit (stolarija/models.py) — dodati:
```python
ai_reminder_sent   = models.BooleanField(default=False)
ai_reminder_at     = models.DateTimeField(null=True, blank=True)
client_email_thread = models.CharField(max_length=200, blank=True)  # email thread ID
ai_sentiment_score = models.FloatField(null=True, blank=True)  # -1.0 do 1.0
ai_image_analysis  = models.JSONField(default=dict, blank=True)
escalated_to_human = models.BooleanField(default=False)
```

---

## GEMINI TASK — što Gemini implementira autonomno

### Task 1: Sentiment analyser
```python
# stolarija/ai_service.py

def analyse_customer_reply(email_text: str, image_base64: str = None) -> dict:
    """
    Gemini Pro Vision analizira odgovor kupca.
    Vraća: {
        'sentiment': float,      # -1.0 (bijes) do 1.0 (zadovoljstvo)
        'intent': str,           # 'book_service' | 'complaint' | 'question' | 'cancel'
        'urgency': str,          # 'low' | 'medium' | 'high' | 'critical'
        'image_issue': str,      # opis problema sa slike (ako postoji)
        'image_confidence': float, # 0-1, ako < 0.7 → traži bolju sliku
        'suggested_reply': str,  # predloženi odgovor (ide na odobrenje)
        'escalate': bool,        # True = prebaci na čovjeka odmah
    }
    """
```

### Task 2: Celery task za automatske remindere
```python
@shared_task(name='stolarija.tasks.service_reminder_batch')
def service_reminder_batch():
    """
    Svaki dan 09:00.
    Pronađi sve ServiceVisit koji idu za 14 dana.
    Generiraj draft email za svaki — ne šalji, samo stavi na odobrenje.
    """
```

### Task 3: Inbound email webhook
Webhook koji hvata odgovore kupaca na service@limit-connect.com
→ Parsira email → poziva analyse_customer_reply → kreira FenixInboxItem

---

## PRAVILA (nema iznimki)

1. AI NIKAD ne šalje email bez Zdenkovog klika "Odobri"
2. Negativan sentiment (score < -0.3) → STOP, eskalacija čovjeku odmah
3. Slika confidence < 0.7 → AI traži bolju sliku, ne nagađa
4. AI potpis u emailu: "Fenix AI asistent | Zdenko Šoš stolarija"
5. Svaki AI email → BookingSignature zapis
6. Termin nikad nije "potvrđen" bez: "Potvrda stiže u roku 2 sata od našeg ureda"

---

## GDPR (Gemini upozorio, ispravno)

- Kupac mora biti informiran da komunicira s AI asistentom
- Pravo na "razgovor s čovjekom" uvijek dostupno — link u svakom emailu
- AI ne smije čuvati slike kupaca dulje od 30 dana (auto-delete)
- Privacy policy mora spominjati AI obradu (COMPLIANCE_SHIELD.md update)

---

## AUTOPILOT — uvjeti

Tek kada su ispunjeni SVI:
□ 100 slučajeva prošlo bez Zdenkovog ispravka
□ 0 eskalacija zbog sentimenta u zadnjih 30 dana
□ Zdenko eksplicitno pristaje pisanom izjavom
□ GDPR audit završen
□ Osiguranje odgovornosti provjereno

## PROCJENA: 4-5 dana Gemini implementacije
```
Dan 1-2: sentiment analyser + Celery task
Dan 3: inbound webhook + FenixInbox integracija  
Dan 4: Dashboard UI za odobravanje (Zdenko panel)
Dan 5: Testiranje s pravim emailovima (sandbox)
```
