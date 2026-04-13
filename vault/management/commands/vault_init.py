"""
Management komanda: vault_init
Inicijalizira trezor — generira VAULT_KEY i postavlja prve članove.

Pokretanje:
  venv/bin/python manage.py vault_init
  venv/bin/python manage.py vault_init --add-member ivan_brtan --trojstvo ALL
"""
import os

from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Inicijalizira LIMIT Connect Trezor (Vault)'

    def add_arguments(self, parser):
        parser.add_argument('--add-member', type=str, help='Username korisnika za dodati kao člana')
        parser.add_argument('--trojstvo', type=str, default='ALL',
                            choices=['T2', 'T3', 'ALL'], help='Trojstvo pristupa')
        parser.add_argument('--can-delete', action='store_true', help='Daje pravo brisanja')
        parser.add_argument('--generate-key', action='store_true', help='Generiraj novi VAULT_KEY')

    def handle(self, *args, **options):
        from vault.models import VaultMember

        # Generiraj ključ
        if options['generate_key']:
            key = Fernet.generate_key().decode()
            self.stdout.write(self.style.SUCCESS('\nNovi VAULT_KEY (dodaj u .env):'))
            self.stdout.write(f'VAULT_KEY={key}\n')
            self.stdout.write(self.style.WARNING(
                'ČUVAJ OVAJ KLJUČ! Bez njega su svi unosi u trezoru nepovratno izgubljeni.\n'
                'Pohrani ga na sigurno mjesto izvan servera.\n'
            ))
            return

        # Provjeri postoji li VAULT_KEY
        vault_key = os.environ.get('VAULT_KEY', '')
        if not vault_key:
            self.stdout.write(self.style.ERROR(
                'VAULT_KEY nije u .env!\n'
                'Pokreni: venv/bin/python manage.py vault_init --generate-key\n'
                'Dodaj rezultat u .env, pa pokreni ovu komandu ponovo.'
            ))
            return

        # Dodaj člana
        if options['add_member']:
            username = options['add_member']
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Korisnik "{username}" ne postoji.'))
                return

            trojstvo = options['trojstvo']
            member, created = VaultMember.objects.get_or_create(
                user=user,
                defaults={
                    'display_name': f'{user.first_name} {user.last_name}'.strip() or username,
                    'trojstvo': trojstvo,
                    'is_active': True,
                    'can_write': True,
                    'can_delete': options['can_delete'],
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(
                    f'✅ Dodan: {member.display_name} '
                    f'[{member.get_trojstvo_display()}]'
                    f'{" + brisanje" if member.can_delete else ""}'
                ))
            else:
                member.trojstvo = trojstvo
                member.is_active = True
                member.can_delete = options['can_delete']
                member.save()
                self.stdout.write(self.style.SUCCESS(
                    f'✅ Ažuriran: {member.display_name} [{member.get_trojstvo_display()}]'
                ))
            return

        # Prikaz stanja
        members = VaultMember.objects.filter(is_active=True).select_related('user')
        self.stdout.write('\n=== LIMIT Connect Trezor — Članovi ===')
        if not members.exists():
            self.stdout.write('  (nema članova — dodaj s --add-member)')
        for m in members:
            self.stdout.write(
                f'  {"✏️ " if m.can_write else "👁️ "}{"🗑️ " if m.can_delete else ""}'
                f'{m.display_name} — {m.get_trojstvo_display()}'
            )

        from vault.models import VaultEntry
        entries = VaultEntry.objects.filter(is_active=True).count()
        self.stdout.write(f'\n  Unosa u trezoru: {entries}')
        self.stdout.write(f'  VAULT_KEY: {"✅ konfiguriran" if vault_key else "❌ nedostaje"}\n')
