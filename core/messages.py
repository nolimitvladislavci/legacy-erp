"""
LIMIT Connect — Centralni sustav poruka korisnicima.

Svaka poruka ima:
 - Jasan opis što se dogodilo
 - Sljedeći korak (ako je primjenjiv)
 - Prijevod na 5 jezika (via Django i18n)

Korištenje:
    from core.messages import msg
    msg.success(request, 'invoice_created', number='RN-2026-0042')
    msg.error(request, 'no_company')
    msg.warn(request, 'low_stock', item='Vijak M8', stock=3, min_qty=10)
"""
from django.contrib import messages
from django.utils.translation import gettext as _


# ═══════════════════════════════════════════════════════════════
# MESSAGE CATALOG — Svaka poruka je (level, template, hint)
# ═══════════════════════════════════════════════════════════════

_CATALOG = {
    # ── AUTH / PRISTUP ────────────────────────────────────────
    'no_company': (
        messages.ERROR,
        _('Niste povezani s tvrtkom.'),
        _('Odaberite tvrtku iz izbornika ili se obratite administratoru.'),
    ),
    'no_company_context': (
        messages.ERROR,
        _('Niste povezani s tvrtkom.'),
        _('Odaberite tvrtku iz izbornika ili se obratite administratoru.'),
    ),
    'no_access': (
        messages.ERROR,
        _('Nemate ovlasti za ovu radnju.'),
        _('Ako mislite da je greška, obratite se administratoru.'),
    ),
    'no_access_company': (
        messages.ERROR,
        _('Nemate pristup ovoj tvrtki.'),
        _('Provjerite jeste li prijavljeni s ispravnim računom.'),
    ),
    'company_not_found': (
        messages.ERROR,
        _('Tvrtka nije pronađena u sustavu.'),
        _('Provjerite podatke i pokušajte ponovo.'),
    ),
    'login_required': (
        messages.WARNING,
        _('Za nastavak je potrebna prijava.'),
        _('Prijavite se s emailom i lozinkom ili PIN-om.'),
    ),
    'session_expired': (
        messages.WARNING,
        _('Vaša sesija je istekla.'),
        _('Prijavite se ponovo za nastavak rada.'),
    ),
    'link_expired': (
        messages.ERROR,
        _('Ovaj link je istekao ili je već iskorišten.'),
        _('Zatražite novi link putem obrasca za resetiranje.'),
    ),
    'account_inactive': (
        messages.ERROR,
        _('Vaš račun je deaktiviran.'),
        _('Kontaktirajte administratora za reaktivaciju.'),
    ),
    'pin_wrong': (
        messages.ERROR,
        _('Neispravan PIN.'),
        None,  # hint se dodaje dinamički (preostali pokušaji)
    ),
    'pin_set': (
        messages.SUCCESS,
        _('PIN uspješno postavljen!'),
        _('Koristite ga za brzu prijavu na radnom mjestu.'),
    ),
    'password_changed': (
        messages.SUCCESS,
        _('Lozinka uspješno promijenjena.'),
        _('Nova lozinka je aktivna od sada.'),
    ),
    'password_mismatch': (
        messages.ERROR,
        _('Lozinke se ne podudaraju.'),
        _('Unesite istu lozinku u oba polja.'),
    ),
    'password_too_short': (
        messages.ERROR,
        _('Lozinka mora imati najmanje 8 znakova.'),
        _('Koristite kombinaciju slova, brojeva i znakova.'),
    ),
    'register_ok': (
        messages.SUCCESS,
        _('Račun kreiran!'),
        _('Provjerite email za verifikacijski link.'),
    ),

    # ── COMPANY SWITCH ────────────────────────────────────────
    'switched': (
        messages.SUCCESS,
        None,  # dinamički: "Prebačeno na: {name}"
        _('Sada radite u kontekstu ove tvrtke.'),
    ),
    'switch_error': (
        messages.ERROR,
        _('Prebacivanje nije uspjelo.'),
        _('Pokušajte ponovo ili odaberite drugu tvrtku iz izbornika.'),
    ),

    # ── INVOICING ─────────────────────────────────────────────
    'invoice_created': (
        messages.SUCCESS,
        None,  # dinamički: "Račun {number} kreiran!"
        _('Pošaljite emailom, ispišite ili fiskalizirajte.'),
    ),
    'invoice_updated': (
        messages.SUCCESS,
        None,  # dinamički
        _('Promjene su spremljene.'),
    ),
    'invoice_sent': (
        messages.SUCCESS,
        None,  # dinamički
        _('Klijent će dobiti obavijest.'),
    ),
    'invoice_storno': (
        messages.SUCCESS,
        None,  # dinamički
        _('Originalni račun je poništen.'),
    ),
    'invoice_fiscal_ok': (
        messages.SUCCESS,
        _('Račun uspješno fiskaliziran!'),
        None,  # hint dinamički: ZKI/JIR
    ),
    'invoice_fiscal_error': (
        messages.ERROR,
        _('Fiskalizacija nije uspjela.'),
        _('Provjerite certifikat i internetsku vezu. Pokušajte ponovo.'),
    ),
    'invoice_locked': (
        messages.WARNING,
        _('Ovaj dokument je zaključan i ne može se mijenjati.'),
        _('Za izmjene kontaktirajte administratora.'),
    ),
    'invoice_save_error': (
        messages.ERROR,
        _('Spremanje dokumenta nije uspjelo.'),
        _('Provjerite sva obavezna polja i pokušajte ponovo.'),
    ),
    'convert_not_allowed': (
        messages.ERROR,
        _('Ova pretvorba nije dozvoljena za ovaj tip dokumenta.'),
        None,
    ),
    'convert_exists': (
        messages.WARNING,
        None,  # dinamički: "Dokument već postoji: {number}"
        _('Kliknite za pregled postojećeg dokumenta.'),
    ),

    # ── POS ───────────────────────────────────────────────────
    'pos_not_configured': (
        messages.ERROR,
        _('POS sustav nije konfiguriran za ovu tvrtku.'),
        _('Otvorite Postavke → POS ili kontaktirajte administratora.'),
    ),
    'pos_session_opened': (
        messages.SUCCESS,
        None,  # dinamički: "Smjena #{number} otvorena!"
        _('Skenirajte artikle ili unesite ručno za kreiranje bona.'),
    ),
    'pos_session_closed': (
        messages.SUCCESS,
        None,  # dinamički: "Smjena #{number} zatvorena."
        _('Z-izvještaj je generiran.'),
    ),
    'pos_session_already_open': (
        messages.WARNING,
        _('Terminal već ima otvorenu smjenu.'),
        _('Zatvorite postojeću smjenu prije otvaranja nove.'),
    ),
    'pos_session_already_closed': (
        messages.WARNING,
        _('Ova smjena je već zatvorena.'),
        _('Otvorite novu smjenu za nastavak rada.'),
    ),
    'pos_receipt_closed': (
        messages.WARNING,
        _('Ovaj bon je zatvoren i ne može se mijenjati.'),
        _('Kreirajte novi bon za novu prodaju.'),
    ),
    'pos_receipt_empty': (
        messages.ERROR,
        _('Bon je prazan — dodajte artikle prije naplate.'),
        _('Skenirajte barcode ili pretražite artikl.'),
    ),
    'pos_item_added': (
        messages.SUCCESS,
        None,  # dinamički: "{desc} x{qty} dodan"
        None,
    ),
    'pos_item_removed': (
        messages.SUCCESS,
        None,  # dinamički: "{name} uklonjen s bona"
        None,
    ),
    'pos_payment_ok': (
        messages.SUCCESS,
        _('Plaćanje evidentirano!'),
        _('Bon je spreman za ispis.'),
    ),
    'pos_low_stock': (
        messages.WARNING,
        None,  # dinamički
        _('Naručite novu količinu.'),
    ),
    'pos_zero_stock': (
        messages.WARNING,
        None,  # dinamički: "{name} — zaliha je 0!"
        _('Nastavite samo ako imate robu fizički na lageru.'),
    ),
    'pos_zero_price': (
        messages.WARNING,
        None,  # dinamički
        _('Provjerite je li cijena ispravna.'),
    ),
    'pos_close_empty': (
        messages.WARNING,
        _('Zatvarate smjenu bez ijednog bona.'),
        _('Ako je namjerno — kliknite ponovo za potvrdu.'),
    ),
    'pos_open_receipts': (
        messages.ERROR,
        None,  # dinamički: "{count} bonova čeka naplatu"
        _('Naplatite ili obrišite otvorene bonove prije zatvaranja.'),
    ),
    'pos_cashier_login': (
        messages.INFO,
        _('Odaberite blagajnika i unesite PIN za otvaranje smjene.'),
        None,
    ),

    # ── DOCUMENTS / ARHIVA ────────────────────────────────────
    'doc_created': (
        messages.SUCCESS,
        None,  # dinamički: "Dokument {number} kreiran."
        _('AI ga analizira u pozadini — provjerite za minutu.'),
    ),
    'doc_booked': (
        messages.SUCCESS,
        None,  # dinamički
        _('Dokument je proknjižen u URA/IRA.'),
    ),
    'doc_deleted': (
        messages.SUCCESS,
        _('Dokument obrisan.'),
        None,
    ),
    'doc_upload_ok': (
        messages.SUCCESS,
        _('Dokument uspješno učitan!'),
        _('AI prepoznavanje je u tijeku — rezultat za nekoliko sekundi.'),
    ),

    # ── WORKSPACE ─────────────────────────────────────────────
    'workspace_switched': (
        messages.SUCCESS,
        None,  # dinamički: "Radite na: {client_name}"
        _('Svi moduli su sada u kontekstu ovog klijenta.'),
    ),
    'no_clients': (
        messages.INFO,
        _('Nemate dodijeljenih klijenata.'),
        _('Administrator vam dodjeljuje klijente u Radnom prostoru.'),
    ),

    # ── GENERIC ───────────────────────────────────────────────
    'generic_error': (
        messages.ERROR,
        _('Nešto je pošlo krivo.'),
        _('Pokušajte ponovo. Ako se nastavi, kontaktirajte podršku.'),
    ),
    'generic_success': (
        messages.SUCCESS,
        _('Uspješno spremljeno.'),
        None,
    ),
    'generic_deleted': (
        messages.SUCCESS,
        _('Uspješno obrisano.'),
        None,
    ),
    'form_errors': (
        messages.ERROR,
        _('Obrazac sadrži greške.'),
        _('Provjerite označena polja i pokušajte ponovo.'),
    ),
    'permission_denied': (
        messages.ERROR,
        _('Nemate ovlasti za ovu radnju.'),
        _('Ako mislite da je greška, obratite se administratoru.'),
    ),
    'module_not_active': (
        messages.WARNING,
        _('Ovaj modul nije aktivan za vašu tvrtku.'),
        _('Aktivirajte ga u Postavke → Moduli ili nadogradite plan.'),
    ),
    'all_clear': (
        messages.SUCCESS,
        _('Sve čisto!'),
        None,
    ),
}


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════

class _MessageGuide:
    """
    Centralni helper za user-facing poruke.

    msg.success(request, 'invoice_created', number='RN-2026-0042')
    msg.error(request, 'no_company')
    msg.warn(request, 'low_stock', item='Vijak M8', stock=3)
    msg.send(request, 'pos_session_opened', number=42)
    """

    def send(self, request, key, text_override=None, hint_override=None, **kwargs):
        """Send a catalogued message. kwargs fill dynamic placeholders."""
        entry = _CATALOG.get(key)
        if not entry:
            # Fallback — unknown key, send as-is
            messages.info(request, key)
            return

        level, text_template, hint_template = entry

        # Build main text
        if text_override:
            text = text_override
        elif text_template:
            try:
                text = text_template.format(**kwargs) if kwargs else text_template
            except (KeyError, IndexError):
                text = text_template
        else:
            text = ''

        # Build hint (next step)
        if hint_override:
            hint = hint_override
        elif hint_template:
            try:
                hint = hint_template.format(**kwargs) if kwargs else hint_template
            except (KeyError, IndexError):
                hint = hint_template
        else:
            hint = ''

        # Compose final message
        if text and hint:
            full = f'{text} · {hint}'
        elif text:
            full = text
        elif hint:
            full = hint
        else:
            full = key  # last resort

        messages.add_message(request, level, full)

    def success(self, request, key_or_text, **kwargs):
        """Shortcut for success messages."""
        if key_or_text in _CATALOG:
            self.send(request, key_or_text, **kwargs)
        else:
            messages.success(request, key_or_text)

    def error(self, request, key_or_text, **kwargs):
        """Shortcut for error messages."""
        if key_or_text in _CATALOG:
            self.send(request, key_or_text, **kwargs)
        else:
            messages.error(request, key_or_text)

    def warn(self, request, key_or_text, **kwargs):
        """Shortcut for warning messages."""
        if key_or_text in _CATALOG:
            self.send(request, key_or_text, **kwargs)
        else:
            messages.warning(request, key_or_text)

    def info(self, request, key_or_text, **kwargs):
        """Shortcut for info messages."""
        if key_or_text in _CATALOG:
            self.send(request, key_or_text, **kwargs)
        else:
            messages.info(request, key_or_text)


# Singleton
msg = _MessageGuide()
