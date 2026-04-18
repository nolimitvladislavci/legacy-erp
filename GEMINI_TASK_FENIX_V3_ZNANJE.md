# GEMINI TASK — FENIX V3 ZNANJE EKSTRAKCIJA
**Agent: Gemini (autonomni) | Koordinator: Sonnet | Max koraka: 15**
**Prioritet: VISOK — paralelno s CC kickoff taskom**

---

## MISIJA

Stari kod je zlato. Ne kopiramo ga — učimo iz njega.
Tvoj zadatak: izvuci 20 najvažnijih poslovnih pravila koja Fenix v3 MORA znati.

---

## ŠTO ČITAŠ

```bash
# Pročitaj ove datoteke redom:
cat /var/www/fina-connect/invoicing/models.py
cat /var/www/fina-connect/accounts/models.py
cat /var/www/fina-connect/companies/models.py
cat /var/www/fina-connect/core/validation_engine.py
cat /var/www/fina-connect/core/route_registry.py
cat /var/www/fina-connect/stolarija/models.py 2>/dev/null || echo "nema"
```

---

## ŠTO TRAŽIŠ

Za svako pravilo:
```
PRAVILO N: [naziv]
Gdje: [app/model/view]
Što radi: [jedna rečenica]
Zašto je kritično: [posljedica ako se izgubi]
Kako implementirati u v3: [konkretna napomena]
```

Posebno pazi na:
1. OIB validacija (Luhn-10) — mora biti identična
2. Fiscalizacija flow — ZKI/JIR generiranje
3. Tenant isolation — company scope na svakom queryu
4. TriKey PIN logika — 2FA flow
5. RouteRegistry pattern — koja ruta treba što
6. Soft delete pattern — je li korišten
7. Umbrella logika — parent/child firme
8. WhatsApp WAHA integracija — koji events
9. GDPR audit log — što se logira
10. Synesis import format — ako se treba ponavljati

---

## FORMAT IZVJEŠTAJA

Spremi kao `/var/www/fenix-v3/GEMINI_ZNANJE_V3.md`

Struktura:
```markdown
# Fenix v3 — Znanje iz starog koda

## Kritična poslovna pravila (20)
[svako pravilo u formatu gore]

## Modeli koje MORA imati v3 (top 10)
[naziv, polja koja su kritična, zašto]

## Integracije koje MORA imati v3
[naziv, endpoint, format]

## Što NE prenosimo (antipatterns)
[što je bilo loše, kako raditi bolje u v3]

## Preporuka za redoslijed modula u v3
[koji modul gradi na čemu]
```

---

## NAPOMENA

Ne deployaš ništa. Ne mijenjaš stari kod.
Samo čitaš i dokumentiraš.
Ovo je temelj na kojem CC gradi v3.
