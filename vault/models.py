"""
LIMIT Connect — Interni Trezor (Vault)
Šifrirani trezor za povjerljive podatke unutar sustava.

Pristup: samo VaultMember korisnici.
Šifriranje: Fernet symmetric (AES-128-CBC) — ključ u .env kao VAULT_KEY.
Svaki pristup se bilježi u VaultAccessLog (nemodificirajuće).

Trojstvo pristupa:
  Trojstvo 2 (Core):    Ivan, Antonio, Marija — ravnopravni, samostalni
  Trojstvo 3 (Ops):     Ivan/Marija, Kruljac, neutral — ravnopravni, samostalni
"""
import os

from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.db import models


def _get_fernet():
    """Inicijalizira Fernet s VAULT_KEY iz .env."""
    key = os.environ.get('VAULT_KEY', '')
    if not key:
        # Ako nema ključa — generiraj i upozori
        import logging
        logging.getLogger('vault').critical(
            'VAULT_KEY nije postavljen u .env! '
            'Pokreni: python manage.py vault_init_key'
        )
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (UnicodeDecodeError, ValueError):
        return None


class VaultCategory(models.TextChoices):
    CREDENTIALS   = 'credentials',   'Pristupni podaci (lozinke, API ključevi)'
    CERTIFICATES  = 'certificates',  'Certifikati (.p12, SSL, FINA)'
    LEGAL         = 'legal',         'Pravni dokumenti (ugovori, punomoći)'
    FINANCIAL     = 'financial',     'Financijski podaci (kartice, bankovni)'
    INFRASTRUCTURE = 'infra',        'Infrastruktura (SSH, server pristup)'
    EMERGENCY     = 'emergency',     'Hitni protokoli i upute'
    OTHER         = 'other',         'Ostalo'


class TrojstvoRole(models.TextChoices):
    TROJSTVO_2 = 'T2', 'Trojstvo 2 — Core (Ivan, Antonio, Marija)'
    TROJSTVO_3 = 'T3', 'Trojstvo 3 — Operativno (Marija, Kruljac, Neutral)'
    ALL        = 'ALL', 'Sva trojstva — puni pristup'


class VaultMember(models.Model):
    """
    Ovlašteni član trezora.
    Svaki član je ravnopravan i samostalan — ne treba suglasnost drugog.
    """
    user         = models.OneToOneField(User, on_delete=models.CASCADE,
                                         related_name='vault_member')
    display_name = models.CharField(max_length=200,
                                    help_text='Ime kako se prikazuje u trezoru')
    trojstvo     = models.CharField(max_length=3, choices=TrojstvoRole.choices,
                                    default=TrojstvoRole.ALL)
    is_active    = models.BooleanField(default=True)
    can_write    = models.BooleanField(default=True,
                                       help_text='Može dodavati i mijenjati unose')
    can_delete   = models.BooleanField(default=False,
                                       help_text='Može brisati unose (samo vlasnik)')
    added_by     = models.ForeignKey(User, on_delete=models.SET_NULL,
                                      null=True, related_name='vault_members_added')
    added_at     = models.DateTimeField(auto_now_add=True)
    notes        = models.TextField(blank=True,
                                    help_text='Napomena (uloga, kontakt, nasljedstvo)')

    class Meta:
        verbose_name = 'Član trezora'
        verbose_name_plural = 'Članovi trezora'
        ordering = ['display_name']

    def __str__(self):
        return f'{self.display_name} [{self.get_trojstvo_display()}]'

    @classmethod
    def is_member(cls, user):
        return cls.objects.filter(user=user, is_active=True).exists()


class VaultEntry(models.Model):
    """
    Šifrirani unos u trezoru.
    Sadržaj je AES šifriran — server ne može pročitati bez VAULT_KEY iz .env.
    """
    title        = models.CharField(max_length=300)
    category     = models.CharField(max_length=20, choices=VaultCategory.choices,
                                    default=VaultCategory.OTHER)
    _content_enc = models.BinaryField(help_text='Šifrirani sadržaj (Fernet AES)')
    url          = models.CharField(max_length=500, blank=True,
                                    help_text='Link (npr. https://hetzner.com)')
    username_hint = models.CharField(max_length=200, blank=True,
                                     help_text='Korisničko ime (nešifrirano — hint)')
    visible_to   = models.CharField(max_length=3, choices=TrojstvoRole.choices,
                                    default=TrojstvoRole.ALL,
                                    help_text='Koje trojstvo može pristupiti')
    priority     = models.CharField(max_length=10,
                                    choices=[('critical','🔴 Kritično'),
                                             ('high','🟡 Visoko'),
                                             ('normal','🟢 Normalno')],
                                    default='normal')
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL,
                                      null=True, related_name='vault_entries_created')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    updated_by   = models.ForeignKey(User, on_delete=models.SET_NULL,
                                      null=True, related_name='vault_entries_updated')
    is_active    = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Unos trezora'
        verbose_name_plural = 'Unosi trezora'
        ordering = ['category', 'title']

    def __str__(self):
        return f'[{self.get_category_display()}] {self.title}'

    def set_content(self, plaintext: str):
        """Šifrira i sprema sadržaj."""
        f = _get_fernet()
        if not f:
            raise ValueError('VAULT_KEY nije konfiguriran')
        encrypted = f.encrypt(plaintext.encode('utf-8'))
        self._content_enc = encrypted

    def get_content(self, requesting_user=None) -> str:
        """Dešifrira i vraća sadržaj. Bilježi pristup."""
        f = _get_fernet()
        if not f:
            raise ValueError('VAULT_KEY nije konfiguriran')
        try:
            decrypted = f.decrypt(bytes(self._content_enc)).decode('utf-8')
        except (UnicodeDecodeError, ValueError):
            raise ValueError('Greška pri dešifriranju — VAULT_KEY možda nije ispravan')

        # Audit log
        if requesting_user:
            VaultAccessLog.objects.create(
                entry=self,
                user=requesting_user,
                action='read',
            )
        return decrypted

    @property
    def content(self):
        """Property za template prikaz — bez audit loga."""
        return self.get_content()


class VaultAccessLog(models.Model):
    """
    Nemodificirajući log svakog pristupa trezoru.
    Tko je pročitao što i kada — forenzički zapis.
    """
    entry      = models.ForeignKey(VaultEntry, on_delete=models.CASCADE,
                                    related_name='access_logs')
    user       = models.ForeignKey(User, on_delete=models.SET_NULL,
                                    null=True, related_name='vault_accesses')
    action     = models.CharField(max_length=10,
                                   choices=[('read','Čitanje'),
                                            ('write','Pisanje'),
                                            ('delete','Brisanje')])
    timestamp  = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'Log pristupa trezoru'
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.user} — {self.action} — {self.entry.title} ({self.timestamp:%d.%m.%Y %H:%M})'
