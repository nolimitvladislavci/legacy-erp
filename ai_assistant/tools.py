"""
Tool definitions for Claude API tool use.
Each tool maps to a handler in tool_handlers.py.
"""

TOOLS = [
    {
        "name": "search_articles",
        "description": "Pretrazi artikle u skladistu po nazivu ili kategoriji. Vraca popis artikala s cijenama i kolicinama.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Pojam za pretragu (naziv artikla)",
                },
                "category": {
                    "type": "string",
                    "description": "Kategorija artikla (material/tool/equipment/consumable/product/service/other)",
                    "enum": ["material", "tool", "equipment", "consumable", "product", "service", "other"],
                },
            },
        },
    },
    {
        "name": "get_expiring_articles",
        "description": "Dohvati artikle kojima uskoro istjece rok trajanja.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "Broj dana unaprijed za provjeru (default 7)",
                    "default": 7,
                },
            },
        },
    },
    {
        "name": "get_today_revenue",
        "description": "Dohvati danasnji promet s POS blagajne — ukupni iznos, broj racuna, porez.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_active_orders",
        "description": "Dohvati aktivne gastro narudzbe (koje nisu placene ili otkazane).",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filtriraj po statusu narudzbe",
                },
            },
        },
    },
    {
        "name": "get_burza_leads",
        "description": "Dohvati leadove s burze projekata.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filtriraj po statusu leada",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maksimalan broj rezultata (default 10)",
                    "default": 10,
                },
            },
        },
    },
    {
        "name": "get_worktime_summary",
        "description": "Dohvati sazetak radnog vremena za trenutnog korisnika.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "Razdoblje: today, week, month (default today)",
                    "enum": ["today", "week", "month"],
                },
            },
        },
    },
    {
        "name": "get_upcoming_appointments",
        "description": "Dohvati nadolazece termine (zakazane i potvrdene).",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "Broj dana unaprijed (default 7)",
                    "default": 7,
                },
            },
        },
    },
    {
        "name": "get_active_interventions",
        "description": "Dohvati aktivne hitne intervencije (koje nisu rijesene/fakturirane).",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_outreach_contacts",
        "description": "Dohvati kontakte iz outreach/CRM modula.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filtriraj po statusu kontakta",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maksimalan broj rezultata (default 10)",
                    "default": 10,
                },
            },
        },
    },
    {
        "name": "get_tracking_status",
        "description": "Dohvati status pracenja po tokenu.",
        "input_schema": {
            "type": "object",
            "properties": {
                "token": {
                    "type": "string",
                    "description": "Javni token za pracenje",
                },
            },
            "required": ["token"],
        },
    },
    {
        "name": "analyze_inventory_value",
        "description": "Sinteticki pregled skladista: ukupna vrijednost zaliha (nabavna i prodajna) te artikli ispod minimalne razine (low stock).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_cashflow_summary",
        "description": "Sinteticki pregled financija (AIR-GAPPED): agregirane sume prihoda i rashoda za zadanu godinu/mjesec. Nema pristup bankovnim racunima.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Godina (npr. 2026). Prazno = trenutna."},
                "month": {"type": "integer", "description": "Mjesec (1-12). Prazno = trenutni."},
            },
        },
    },
    {
        "name": "get_pending_payments",
        "description": "Sinteticki pregled placanja na cekanju (pending/processing). Sigurnosno izolirano.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_system_health_check",
        "description": "Pokrece provjeru zdravlja sustava: baza podataka, Redis cache, Celery worker, disk prostor, zadnji error u logu. Vraca status svakog servisa.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "validate_pos_math",
        "description": "Simulira POS racun u memoriji (bez spremanja u bazu) sa zadanim stavkama i provjerava matematiku: subtotal, PDV, total, kusur. Korisno za provjeru ispravnosti POS motora.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "Lista stavki. Svaka stavka: {name, qty, price, tax_rate, discount_pct}",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "qty": {"type": "number"},
                            "price": {"type": "number"},
                            "tax_rate": {"type": "number", "description": "PDV stopa (25, 13, 5)"},
                            "discount_pct": {"type": "number", "description": "Popust u postocima (0-100)"},
                        },
                    },
                },
                "amount_paid": {"type": "number", "description": "Iznos koji kupac placa (za izracun kusura)"},
            },
            "required": ["items"],
        },
    },
    {
        "name": "run_test_suite",
        "description": "Pokrece Django test suite (ili specificni test modul) i vraca rezultat: koliko testova proslo, palo, greske. Moze pokrenuti sve testove ili samo odredjeni modul.",
        "input_schema": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "Naziv test modula (npr. 'tests.test_pos_propter_integration'). Prazno = svi testovi.",
                }
            },
        },
    },
    {
        "name": "audit_data_integrity",
        "description": "Provjerava integritet podataka: orphan zapisi (profili bez korisnika, racuni bez sesija), duplikati, nekonzistentni statusi. Vraca listu problema.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "explain_business_flow",
        "description": "Objasnjava poslovni tok/pipeline u sustavu. Moze objasniti: pos (POS naplata), propter (otpremnice->eracun), fiscal (fiskalizacija), eracun (e-Racun pipeline), inventory (zalihe), payments (placanja).",
        "input_schema": {
            "type": "object",
            "properties": {
                "flow": {
                    "type": "string",
                    "description": "Naziv toka: pos, propter, fiscal, eracun, inventory, payments, smart_import",
                }
            },
            "required": ["flow"],
        },
    },
    {
        "name": "get_worktime_report",
        "description": "Izvjestaj radnih sati. Moze filtrirati po radniku (user_id ili username), radnoj grupi (group_id), projektu (project_code), datumskom rasponu (date_from, date_to). Vraca agregirane sate, billing iznos, breakdown po radniku/projektu.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "ID radnika (opcionalno)"},
                "username": {"type": "string", "description": "Username radnika (opcionalno)"},
                "group_id": {"type": "integer", "description": "ID radne grupe (opcionalno)"},
                "project_code": {"type": "string", "description": "Kod projekta npr. PRJ-001 (opcionalno)"},
                "date_from": {"type": "string", "description": "Pocetak perioda YYYY-MM-DD (default: prvi u mjesecu)"},
                "date_to": {"type": "string", "description": "Kraj perioda YYYY-MM-DD (default: danas)"},
                "status": {
                    "type": "string",
                    "description": "Filter po statusu: APPROVED, PENDING, DRAFT, all (default: all)",
                },
                "only_unbilled": {"type": "boolean", "description": "Samo neobracunati sati (default: false)"},
            },
        },
    },
    {
        "name": "preview_invoice_from_hours",
        "description": "SUHI PREGLED (dry run): Pokazuje kako bi izgledao racun kreiran iz neobracunatih radnih sati za odabrani projekt ili radnika. NE sprema nista u bazu. Vraca stavke, iznose, PDV.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_code": {"type": "string", "description": "Kod projekta (obavezno ako nema user_id)"},
                "user_id": {
                    "type": "integer",
                    "description": "ID radnika (opcionalno - filtrira sate samo tog radnika)",
                },
                "date_from": {"type": "string", "description": "Od datuma YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "Do datuma YYYY-MM-DD"},
                "tax_rate": {"type": "number", "description": "PDV stopa (default: 25)"},
                "group_by": {
                    "type": "string",
                    "description": "Grupiranje stavki: 'worker' (po radniku), 'task' (po tipu zadatka), 'day' (po danu). Default: worker",
                },
            },
            "required": ["project_code"],
        },
    },
    {
        "name": "create_invoice_from_hours",
        "description": "KREIRA RACUN iz neobracunatih radnih sati. Stavke se grupiraju po radniku. Sati se oznacavaju kao is_billed=True i povezuju s kreiranim racunom. OPREZ: ova akcija mijenja podatke u bazi.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_code": {"type": "string", "description": "Kod projekta (obavezno)"},
                "user_id": {"type": "integer", "description": "Samo sati ovog radnika (opcionalno)"},
                "date_from": {"type": "string", "description": "Od datuma YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "Do datuma YYYY-MM-DD"},
                "tax_rate": {"type": "number", "description": "PDV stopa (default: 25)"},
                "client_name": {
                    "type": "string",
                    "description": "Naziv klijenta (override, inace se koristi project.client_name)",
                },
                "note": {"type": "string", "description": "Napomena na racunu"},
                "payment_days": {"type": "integer", "description": "Rok placanja u danima (default: 15)"},
            },
            "required": ["project_code"],
        },
    },
    # --- Fenix Intelligence v2 tools (CC Code) ---
    {
        "name": "get_fund_opportunities",
        "description": "Dohvati relevantne EU fondove i HR poticaje za firmu. Filtrira po tipu firme (OPG, udruga, d.o.o.), roku prijave i iznosu. Koristi Intelligence modul.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tip": {
                    "type": "string",
                    "description": "Tip: eu_fond, hr_poticaj, bio_certifikacija, sve (default: sve)",
                    "enum": ["eu_fond", "hr_poticaj", "bio_certifikacija", "sve"],
                },
                "rok_dana": {"type": "integer", "description": "Fondovi koji isticu za N dana (default: 90)"},
                "samo_aktivni": {"type": "boolean", "description": "Samo aktivni natjecaji (default: true)"},
            },
        },
    },
    {
        "name": "get_livestock_status",
        "description": "Status farme goveda za OPG. Broj grla, zdravstveni alarmi, mlijeko danas, krave koje tele uskoro, plan sjetve. Samo za OPG firme.",
        "input_schema": {
            "type": "object",
            "properties": {
                "detalji": {
                    "type": "string",
                    "description": "Sto prikazati: pregled, zdravlje, mlijeko, usjevi (default: pregled)",
                    "enum": ["pregled", "zdravlje", "mlijeko", "usjevi"],
                }
            },
        },
    },
    {
        "name": "create_futures_listing",
        "description": "ASSISTED: Objavi visak usjeva ili proizvoda na Burzi kao FuturesListing. Prolazi kroz AIGate ASSISTED razinu -- ceka potvrdu vlasnika. Samo za OPG firme.",
        "input_schema": {
            "type": "object",
            "properties": {
                "crop_plan_id": {
                    "type": "integer",
                    "description": "ID CropPlana ciji visak objavljujemo (iz get_livestock_status usjevi)",
                },
                "cijena_eur_t": {"type": "number", "description": "Cijena u EUR po toni (OPG postavlja)"},
                "napomena": {"type": "string", "description": "Napomena za listing (opcionalno)"},
            },
            "required": ["crop_plan_id"],
        },
    },
    {
        "name": "get_compliance_warnings",
        "description": "Prediktivna compliance provjera: PDV granica, istekli dokumenti vozila/vozaca, membership expiry, karencija goveda, EU fond rokovi. AI upozorava PRIJE problema.",
        "input_schema": {
            "type": "object",
            "properties": {
                "kategorija": {
                    "type": "string",
                    "description": "Kategorija: sve, pdv, dokumenti, clanarine, livestock, fondovi (default: sve)",
                    "enum": ["sve", "pdv", "dokumenti", "clanarine", "livestock", "fondovi"],
                }
            },
        },
    },
    # CC Code prijedlog: get_intelligence_results -- korisnik pita "sto si nasao?" / "ima li novih pronalazaka"
    {
        "name": "get_intelligence_results",
        "description": "Dohvati najnovije Intelligence pronalaske (FundOpportunity, trzisne cijene, agro vijesti) za firmu. Koristiti kad korisnik pita 'sto si nasao', 'ima li novih pronalazaka', 'novosti'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter po statusu: novo, obavljeno, odbaceno, sve (default: novo)",
                    "enum": ["novo", "obavljeno", "odbaceno", "sve"],
                },
                "limit": {"type": "integer", "description": "Maksimalan broj rezultata (default: 10)"},
            },
        },
    },
]
