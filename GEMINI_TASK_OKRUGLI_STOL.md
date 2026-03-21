## PRVO PROCITAJ STATUS
```bash
cat /var/www/fina-connect/FENIX_STATUS.md
```

# GEMINI TASK — Analiza: Okrugli stol arhitektura i prava pristupa

## Što je okrugli stol
Interaktivni SVG widget u LIMIT Connect sustavu.
Nalazi se na:
- `/hr/tim-chat/` — za sve korisnike (Šeki, Marija, ostali)
- `/hr/superadmin/ivan/` — Ivan Cockpit (samo superadmin)

## Arhitektura

### tim_chat view (core/views.py)
```python
@login_required
def tim_chat(request):
    from pos.models import ImprovementSuggestion
    qs = ImprovementSuggestion.objects.filter(
        author=request.user
    ).order_by('-created_at')[:10]
    return render(request, 'dashboards/tim_chat.html', {'user_messages': qs})
```

### submit_request endpoint (superadmin_ai/views.py)
- URL: `/hr/superadmin/ai/api/submit-request/`
- Prima: `{description, module, priority}`
- Kreira: `PendingAIAction` objekt
- Vraća: `{'ok': True, 'id': '...'}`

### Sjedišta za stolom
| Sjedište | Korisnik | Boja | Tip slanja |
|---|---|---|---|
| Ivan | Vlasnik | gold | WhatsApp |
| Šeki | Uvijek Friško | amber | submit-request |
| Marija | Konjik | green | submit-request |
| CC | Claude Code | blue | submit-request (task) |
| Sonnet | Koordinator | purple | claude.ai link |

## Tvoja pitanja

### PITANJE 1: Sigurnost pristupa
submit-request je na `/superadmin/ai/api/` — što znači da regularni
korisnici (Šeki, Marija) šalju zahtjeve na superadmin endpoint.
Je li ovo sigurnosni problem? Što bi moglo poći po krivu?

### PITANJE 2: Povratna informacija
Šeki pošalje poruku kroz okrugli stol → PendingAIAction se kreira.
Ali Šeki ne vidi odgovor — nema feedback loopa.
Kako preporučaš implementirati odgovor natrag korisniku?

### PITANJE 3: Razlika superadmin vs regularni korisnik
Superadmin (Ivan) vidi okrugli stol s opcijom pisanja svima.
Regularni korisnik vidi jednostavnu formu.
Je li ova distinkcija ispravna? Što bi promijenio?

### PITANJE 4: Nagazne mine
Koje su 3 najveće nagazne mine u ovoj arhitekturi koje bismo
mogli nagaziti u produkciji s pravim korisnicima?

## Format odgovora
Direktno, kratko. Ovo nije akademski rad.
