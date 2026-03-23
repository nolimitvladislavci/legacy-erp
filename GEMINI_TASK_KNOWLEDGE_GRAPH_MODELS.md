# GEMINI_TASK — KNOWLEDGE GRAPH MODEL DEFINITIONS
# Agent: Gemini Pro 2.5  
# Prioritet: KRITIČAN — NI JEDAN RED KODA dok ovo nije DONE
# Datum: 2026-03-24
# Status: ČEKA Geminijev odgovor s finalnim Django modelima

## KONTEKST
Server provjera izvršena. Ključne činjenice:
- Django app: limit_connect_ai/ POSTOJI s modelima AIAgentMission, AIReportLog, ComplianceWatchItem, CampaignPlan
- NEMA odvojenog limit-connect.com direktorija — sve je /var/www/fina-connect/
- Nginx: limit-connect.com → 127.0.0.1:8000 (gunicorn socket)
- client_max_body_size: 50M
- payroll app POSTOJI — Employee model je tamo

## ZADATAK ZA GEMINI

Generiraj FINALNE Django modele za Knowledge Graph koji se dodaju u:
/var/www/fina-connect/limit_connect_ai/models.py

### MODELI KOJE TREBAŠ DEFINIRATI (6 novih):

1. RegulatorySource
   - name, jurisdiction (HR/DE/EU), feed_url, feed_type (rss/api/scrape)
   - check_interval_hours, last_checked, is_active
   - Veza s INSTALLED_APPS: standalone (nema FK na company — globalni izvor)

2. RegulatoryUpdate  
   - source (FK→RegulatorySource), raw_text, content_hash (SHA256, za duplikate)
   - published_date, ingested_at, processed (bool), jurisdiction
   - NAPOMENA: content_hash mora biti unique — nema duplikata

3. LegalEntity
   - update (FK→RegulatoryUpdate), article_ref (npr. "§19 UStG")
   - content_text, effective_from (date), effective_until (date, nullable)
   - entity_type (article/paragraph/clause/definition)
   - NAPOMENA: jedan RegulatoryUpdate → više LegalEntity (one-to-many)

4. ImpactDomain
   - legal_entity (FK→LegalEntity)
   - nkd_codes (JSONField, lista string-ova)
   - revenue_threshold_min, revenue_threshold_max (DecimalField, nullable)
   - employee_count_min, employee_count_max (IntegerField, nullable)
   - jurisdiction_scope (CharField: HR/DE/EU/ALL)

5. AdaptationRule
   - legal_entity (FK→LegalEntity), impact_domain (FK→ImpactDomain)
   - rule_type (choices: tax_rate/threshold/report_format/deadline/other)
   - action_code (CharField: "update_vat_rate" / "update_pausal_limit" itd.)
   - action_params (JSONField: {"field": "vat_rate", "value": 0.25})
   - effective_date, auto_apply (bool, default False — SIGURNOSNA MJERA)
   - approved_by (FK→User, nullable — netko mora odobriti auto-apply)

6. LegalOpportunity ★ (CORE MODEL)
   - legal_entity (FK→LegalEntity)
   - opportunity_type (choices: tax_exemption/deduction/subsidy/fund/threshold/deferral)
   - title (CharField, max 200)
   - description (TextField)
   - trigger_conditions (JSONField — parametri za matching s Company)
   - estimated_value_formula (CharField: "revenue * 0.19")
   - estimated_value_eur (DecimalField, nullable — static estimate)
   - risk_level (choices: low/medium/high)
   - confidence_score (FloatField, 0.0-1.0, default 1.0)
   - confidence_last_validated (DateTimeField)
   - action_required (TextField)
   - source_reference (CharField: "§19 UStG abs. 1")
   - is_active (BooleanField)
   - valid_until (DateField, nullable)

### BRIDŽ MODEL (veza Opportunity ↔ Company):
CompanyOpportunity (nadogradnja na postojeći ComplianceWatchItem ili novi model)
   - company (FK→Company)
   - opportunity (FK→LegalOpportunity)
   - match_score (FloatField: estimated_value * confidence / effort)
   - status (choices: detected/notified/accepted/rejected/applied/expired)
   - notified_at, applied_at
   - estimated_value_for_company (DecimalField — personalizirana procjena)
   - notes

## TRI SCENARIJA — parametri za trigger_conditions

### Scenarij A — §19 UStG DE (Kleinunternehmer)
```json
{
  "jurisdiction": "DE",
  "company_revenue_lt": 22000,
  "company_vat_registered": false,
  "excluded_nkd": ["6820", "6430", "6491"]
}
```
formula: "company.annual_revenue * 0.19"

### Scenarij B — HR HZMO mladi (< 30 god)
```json
{
  "jurisdiction": "HR", 
  "employee_age_lt": 30,
  "employment_contract": ["full_time", "part_time"],
  "employment_start_after": "2022-01-01"
}
```
formula: "employee_count_under_30 * avg_gross_salary * 0.075 * 12"

### Scenarij C — EU/DE Digitalizacija MSP
```json
{
  "jurisdiction": ["DE", "HR"],
  "employee_count_between": [1, 249],
  "revenue_lt": 50000000,
  "has_erp_investment": true,
  "last_fund_application_months_ago_gt": 36
}
```
formula: "min(digital_investment * 0.40, 17000)"

## ŠTO GEMINI ISPORUČUJE

Generiraj:
1. Kompletan Python kod za 6+1 modela (Django ORM, s Meta klasama, __str__, properties)
2. Finalni JSON fixture za RegulatorySource (8 izvora s pravim URL-ovima)
3. Tri LegalOpportunity objekta za gornje scenarije (JSON fixture)
4. Opportunity matcher funkciju: match_opportunities_for_company(company) → QuerySet

## VETO PRAVILO
Claude Code NE SMIJE pisati niti jedan model dok Gemini ne isporuči ovaj task.
Sonnet pregleda Geminijev output, Ivan odobrava, TADA CC Code implementira.

## DOSTAVI KAO:
Jedan Python fajl (models_knowledge_graph.py) koji Sonnet pregleda
i jedan JSON fixtures fajl (initial_legal_opportunities.json)
