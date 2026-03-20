from django.db import models


class Member(models.Model):
    MEMBERSHIP_CHOICES = [
        ('basic', 'Osnovno'),
        ('standard', 'Standard'),
        ('premium', 'Premium'),
        ('vip', 'VIP'),
    ]
    STATUS_CHOICES = [
        ('active', 'Aktivan'),
        ('inactive', 'Neaktivan'),
        ('frozen', 'Zamrznut'),
        ('expired', 'Isteklo'),
    ]
    partner = models.OneToOneField('partners.Partner', on_delete=models.CASCADE,
                                    related_name='fitness_member', null=True, blank=True,
                                    verbose_name='Partner')
    first_name = models.CharField(max_length=100, verbose_name='Ime')
    last_name = models.CharField(max_length=100, verbose_name='Prezime')
    email = models.EmailField(blank=True, verbose_name='Email')
    phone = models.CharField(max_length=50, blank=True, verbose_name='Telefon')
    membership_type = models.CharField(max_length=20, choices=MEMBERSHIP_CHOICES,
                                        default='basic', verbose_name='Tip clanstva')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                               default='active', verbose_name='Status')
    date_joined = models.DateField(auto_now_add=True, verbose_name='Datum uclanjenja')
    membership_expires = models.DateField(null=True, blank=True, verbose_name='Istjece clanstvo')
    rfid_card = models.CharField(max_length=50, blank=True, verbose_name='RFID kartica')
    notes = models.TextField(blank=True, verbose_name='Napomene')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fitness_member'
        verbose_name = 'Clan fitnessa'
        verbose_name_plural = 'Clanovi fitnessa'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.membership_type})"


class MemberCheckIn(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE,
                                related_name='checkins', verbose_name='Clan')
    check_in = models.DateTimeField(auto_now_add=True, verbose_name='Dolazak')
    check_out = models.DateTimeField(null=True, blank=True, verbose_name='Odlazak')

    class Meta:
        verbose_name = 'Evidencija dolaska'
        verbose_name_plural = 'Evidencija dolazaka'
        ordering = ['-check_in']

    def __str__(self):
        return f"{self.member} - {self.check_in.strftime('%d.%m.%Y %H:%M')}"
