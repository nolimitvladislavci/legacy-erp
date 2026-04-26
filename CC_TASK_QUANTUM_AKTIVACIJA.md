# CC_TASK: QUANTUM_AKTIVACIJA — Podizanje sigurnosti R1→R3
## Agent: CC Code | Prioritet: KRITIČAN | Rok: sljedeća sesija

---

## ZADATAK 1 — liboqs instalacija (30 min)

```bash
apt-get install -y cmake ninja-build libssl-dev python3-dev
pip install liboqs-python==0.11.0 --break-system-packages
```

Verifikacija:
```bash
python3 -c "
import oqs
kems = oqs.get_enabled_kem_mechanisms()
sigs = oqs.get_enabled_sig_mechanisms()
print('KEM:', [k for k in kems if 'Kyber' in k])
print('SIG:', [s for s in sigs if 'Dilithium' in s])
"
```

Očekivani output:
```
KEM: ['Kyber512', 'Kyber768', 'Kyber1024']
SIG: ['Dilithium2', 'Dilithium3', 'Dilithium5']
```

---

## ZADATAK 2 — argon2-cffi instalacija (10 min)

```bash
pip install argon2-cffi --break-system-packages
```

Ažurirati `/var/www/fina-connect/documents/dok_crypto.py`:
- Zamijeniti `hashlib.pbkdf2_hmac("sha256", ...)` s Argon2id
- Čuvati backward compatibility za stare .dok fajlove (PBKDF2 ostaje za dekriptiranje starih)
- Novi .dok fajlovi = Argon2id(time_cost=3, memory_cost=65536, parallelism=4)

---

## ZADATAK 3 — blake3 instalacija (10 min)

```bash
pip install blake3 --break-system-packages
```

Ažurirati `/var/www/fenix-v3/documents/dok_crypto.py`:
- BLAKE3 kao primarni hash za fingerprint u ChainBlock
- SHA-256 ostaje kao secondary hash za backward compat

---

## ZADATAK 4 — Nginx security headers (20 min)

Dodati u SVE server blokove u `/etc/nginx/sites-enabled/`:

```nginx
server_tokens off;
more_clear_headers Server;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=(), payment=()" always;
add_header X-XSS-Protection "1; mode=block" always;
```

Za limit-connect.com dodati i:
```nginx
add_header Content-Security-Policy "default-src 'self' https:; script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com;" always;
```

---

## ZADATAK 5 — Celery systemd fix (10 min)

```bash
# Provjeri postoje li service fajlovi
ls /etc/systemd/system/celery-fina.service
ls /etc/systemd/system/fenix-v3-celery.service

# Ako ne postoje — kreiraj:
cat > /etc/systemd/system/celery-fina.service << 'EOF'
[Unit]
Description=Celery Worker — fina-connect
After=network.target postgresql.service redis.service

[Service]
User=www-data
WorkingDirectory=/var/www/fina-connect
ExecStart=/var/www/fina-connect/venv/bin/celery -A core worker -l info -Q default,ai,notifications --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable celery-fina
systemctl start celery-fina
systemctl status celery-fina
```

---

## ZADATAK 6 — Redis lozinka (15 min)

```bash
# Generiraj lozinku
REDIS_PASS=$(openssl rand -hex 32)
echo "Redis lozinka: $REDIS_PASS"

# Postavi u Redis
redis-cli CONFIG SET requirepass "$REDIS_PASS"
redis-cli CONFIG REWRITE

# Ažuriraj .env u oba projekta
echo "REDIS_PASSWORD=$REDIS_PASS" >> /var/www/fina-connect/.env
echo "REDIS_PASSWORD=$REDIS_PASS" >> /var/www/fenix-v3/.env
```

Ažurirati settings.py u oba projekta:
```python
REDIS_PASS = os.environ.get("REDIS_PASSWORD", "")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://:{REDIS_PASS}@127.0.0.1:6379/1",
    }
}
```

---

## ZADATAK 7 — TLS 1.3 only na svim domenama

U `/etc/nginx/sites-enabled/`:
- Zamijeniti `ssl_protocols TLSv1.2 TLSv1.3;`
- S `ssl_protocols TLSv1.3;`

Na svim domenama OSIM ako postoji poznati klijent koji koristi TLS 1.2 (stari uređaji).

---

## ZADATAK 8 — Honeypot zapisi u bazi

```python
# Pokrenuti kao manage.py shell
from companies.models import Company
from accounts.models import User

# Honeypot firma — ako ju itko upita, alarm
Company.objects.create(
    name="__HONEYPOT_SENTINEL_001__",
    oib="00000000001",
    is_active=False,
    # posebna zastavica ako postoji
)

# Honeypot korisnik
User.objects.create_user(
    username="__honeypot_user_001__",
    email="honeypot@no-reply.invalid",
    is_active=False,
)
```

U Sentinel middleware dodati check: ako query vrati `__HONEYPOT__` → SentinelAlert(severity='critical').

---

## VERIFIKACIJA NAKON SVIH ZADATAKA

```bash
# 1. Kyber aktivan
python3 -c "import oqs; print('KYBER OK')"

# 2. Argon2 aktivan
python3 -c "import argon2; print('ARGON2 OK')"

# 3. BLAKE3 aktivan
python3 -c "import blake3; print('BLAKE3 OK')"

# 4. Nginx headers
curl -I https://limit-connect.com | grep -E "X-Content|X-Frame|server"

# 5. Celery aktivni servisi
systemctl is-active celery-fina fenix-v3-celery

# 6. Redis lozinka
redis-cli ping  # treba NOAUTH grešku bez lozinke

# 7. TLS test
openssl s_client -connect limit-connect.com:443 2>&1 | grep "Protocol"
```

---

## BILJEŠKA ZA SLJEDEĆEG AGENTA

Nakon što su sve instalacije gotove:
1. Pokrenuti `manage.py check` na oba projekta
2. Pokrenuti test suite: `cd /var/www/fenix-v3 && python manage.py test`
3. Updateati FENIX_STATUS.md i FENIX_ZAKON.md s novim Zakonom 25 (PQC aktivna)
4. Git commit: `security(pqc): liboqs + argon2 + blake3 + nginx headers`
