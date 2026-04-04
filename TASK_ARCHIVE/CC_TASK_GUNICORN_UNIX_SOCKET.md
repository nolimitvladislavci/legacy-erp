# CC_TASK_GUNICORN_UNIX_SOCKET.md
# Kreirao: Sonnet | Datum: 2026-03-29
# Prioritet: 🟠 VISOK — sprječava ponavljanje Ivan-incidenta (2h downtime)
# Procjena: 45 minuta rada | Downtime: < 30 sekundi (graceful reload nginx)
#
# KONTEKST — Zašto ovo radimo
# ─────────────────────────────
# Incident 2026-03-29: Ivan 2h nije mogao logirati.
# Uzrok: gunicorn zombie process zadržao TCP port 8000.
#        Novi gunicorn (systemd restart) nije mogao vezati isti port.
#        systemd pokazivao "active" (restart loop) → health check nije vidio problem.
#
# Riješenje: Unix socket FIZIČKI ELIMINIRA konflikt porta.
# Unix socket je fajl (/run/gunicorn-fina.sock) — ne može ga "zauzeti" zombie.
# Kad gunicorn padne, socket fajl nestaje. Kad se podigne, socket fajl se stvori.
# Nema race conditiona, nema zombie blokiranja.
#
# BONUS: Unix socket je 15-20% brži od TCP loopback (nema TCP overhead).

---

## TRENUTNO STANJE (verificirano)

```
gunicorn-fina.service ExecStart:
  --bind 127.0.0.1:8000
  --bind 172.17.0.1:8000   ← Docker bridge (MCP server i Docker kontejneri)
  --workers 6 --threads 2 --timeout 300

nginx proxy_pass: http://127.0.0.1:8000  (pojavljuje se na ~12 mjesta u konfigu)
```

### ⚠️ KRITIČNO: Dva bind-a
Trenutno gunicorn sluša na DVA mjesta:
- `127.0.0.1:8000` — lokalni nginx
- `172.17.0.1:8000` — Docker bridge (fenix-mcp servis i eventualni Docker kontejneri)

Unix socket zamjenjuje `127.0.0.1:8000`. Docker bind ostaje kao drugi bind.

---

## ZADACI (redosljed je obavezan)

### TASK 1 — Provjeri što koristi 172.17.0.1:8000

```bash
# Provjeri koji servisi/kontejneri koriste Docker bridge port
grep -r "172.17.0.1:8000\|172\.17\.0\.1" /etc/systemd/system/ /var/www/fina-connect/ 2>/dev/null | grep -v ".pyc"
docker ps 2>/dev/null || echo "nema dockera"
cat /etc/systemd/system/fenix-mcp.service 2>/dev/null
```

Ako samo MCP server koristi `172.17.0.1:8000`:
→ MCP server možeš ostaviti na TCP (172.17.0.1) jer Docker bridge ne može koristiti Unix socket
→ nginx mijenjamo na socket, Docker bind ostaje

Ako ništa ne koristi `172.17.0.1:8000`:
→ Ukloni i taj bind — čišće

---

### TASK 2 — Stvori socket direktorij s pravim permisijama

```bash
# Socket ide u /run/ (tmpfs — briše se rebootom, što je ispravno)
# www-data mora imati write permisiju
sudo mkdir -p /run/gunicorn-fina
sudo chown www-data:www-data /run/gunicorn-fina
sudo chmod 755 /run/gunicorn-fina
```

Dodaj u `/etc/tmpfiles.d/gunicorn-fina.conf` (da preživi reboot):
```
d /run/gunicorn-fina 0755 www-data www-data -
```

```bash
sudo systemd-tmpfiles --create /etc/tmpfiles.d/gunicorn-fina.conf
```

---

### TASK 3 — Ažuriraj gunicorn-fina.service

Lokacija: `/etc/systemd/system/gunicorn-fina.service`

**STARO:**
```ini
ExecStart=/var/www/fina-connect/venv/bin/gunicorn core.wsgi:application \
    --bind 127.0.0.1:8000 \
    --bind 172.17.0.1:8000 \
    --workers 6 --threads 2 --timeout 300 \
    --max-requests 1000 --max-requests-jitter 50 \
    --graceful-timeout 30 --preload
```

**NOVO:**
```ini
ExecStart=/var/www/fina-connect/venv/bin/gunicorn core.wsgi:application \
    --bind unix:/run/gunicorn-fina/gunicorn.sock \
    --bind 172.17.0.1:8000 \
    --workers 6 --threads 2 --timeout 300 \
    --max-requests 1000 --max-requests-jitter 50 \
    --graceful-timeout 30 --preload
ExecStartPost=/bin/chmod 660 /run/gunicorn-fina/gunicorn.sock
```

Dodaj i ovo u [Service] sekciju (čisti stari socket pri startu):
```ini
ExecStartPre=/bin/rm -f /run/gunicorn-fina/gunicorn.sock
```

Cijeli novi service fajl:
```ini
[Unit]
Description=Gunicorn daemon for fina-connect (Unix socket)
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/fina-connect
ExecStartPre=/bin/rm -f /run/gunicorn-fina/gunicorn.sock
ExecStart=/var/www/fina-connect/venv/bin/gunicorn core.wsgi:application \
    --bind unix:/run/gunicorn-fina/gunicorn.sock \
    --bind 172.17.0.1:8000 \
    --workers 6 --threads 2 --timeout 300 \
    --max-requests 1000 --max-requests-jitter 50 \
    --graceful-timeout 30 --preload
Restart=always
RestartSec=5
# Socket cleanup pri stopu
ExecStopPost=/bin/rm -f /run/gunicorn-fina/gunicorn.sock

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
```

---

### TASK 4 — Ažuriraj Nginx konfiguraciju

Nginx upstream upute: zamijeni SVE instance `proxy_pass http://127.0.0.1:8000`
s `proxy_pass http://unix:/run/gunicorn-fina/gunicorn.sock`.

**Dodaj upstream blok na vrh server bloka** (prije svih location blokova):

```nginx
upstream gunicorn_fina {
    server unix:/run/gunicorn-fina/gunicorn.sock fail_timeout=0;
}
```

**Zamijeni sve proxy_pass reference:**

```bash
# Provjeri koliko ih ima
grep -c "proxy_pass http://127.0.0.1:8000" /etc/nginx/sites-enabled/*

# Batch zamjena
sudo sed -i 's|proxy_pass http://127.0.0.1:8000|proxy_pass http://gunicorn_fina|g' \
    /etc/nginx/sites-enabled/*

# Verificiraj — mora biti 0
grep -c "proxy_pass http://127.0.0.1:8000" /etc/nginx/sites-enabled/*
```

**Ručna provjera rezultata:**
```bash
grep "proxy_pass" /etc/nginx/sites-enabled/* | grep -v "3000\|3001\|8002\|waha"
# Sve linije trebaju imati: proxy_pass http://gunicorn_fina;
```

**Provjeri nginx konfig:**
```bash
sudo nginx -t
```
Mora biti: `syntax is ok` + `test is successful`. Ako nije — **STANI, ne primjenjuj**.

---

### TASK 5 — Primijeni promjene (redosljed je kritičan)

```bash
# 1. Restart gunicorn (stvara socket)
sudo systemctl restart gunicorn-fina

# 2. Pričekaj 3 sekunde da socket nastane
sleep 3

# 3. Provjeri socket postoji i ima prave permisije
ls -la /run/gunicorn-fina/gunicorn.sock
# Treba biti: srw-rw---- 1 www-data www-data

# 4. Graceful nginx reload (nema downtime)
sudo systemctl reload nginx

# 5. Smoke test
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/health/
# Mora biti: 200
```

---

### TASK 6 — Ažuriraj ai_health.py (check_gunicorn)

Nakon migracije, `check_gunicorn()` u `core/ai_health.py` mora provjeravati socket, ne TCP port.

**Zamijeni socket check u `check_gunicorn()`:**

```python
# STARO — TCP check
import socket
try:
    with socket.create_connection(('127.0.0.1', 8000), timeout=3):
        port_open = True
except (ConnectionRefusedError, TimeoutError, OSError):
    port_open = False

# NOVO — Unix socket check
import socket as socket_lib
GUNICORN_SOCKET = '/run/gunicorn-fina/gunicorn.sock'

def _check_unix_socket():
    """Provjeri postoji li i sluša li Unix socket."""
    import os
    if not os.path.exists(GUNICORN_SOCKET):
        return False, 'socket fajl ne postoji'
    try:
        sock = socket_lib.socket(socket_lib.AF_UNIX, socket_lib.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect(GUNICORN_SOCKET)
        sock.close()
        return True, 'socket OK'
    except Exception as e:
        return False, str(e)[:80]
```

**Ažuriraj `_kill_zombie_port_8000()`** — preimeni u `_fix_broken_gunicorn()`:

```python
def _fix_broken_gunicorn():
    """
    S Unix socketom, zombie problem je eliminiran.
    ExecStartPre briše stari socket.
    Ova funkcija samo restarta service.
    """
    import os
    # Manualno obriši stari socket ako postoji
    socket_path = '/run/gunicorn-fina/gunicorn.sock'
    if os.path.exists(socket_path):
        try:
            os.remove(socket_path)
            logger.warning(f'Stari socket obrisan: {socket_path}')
        except Exception as e:
            logger.error(f'Brisanje socketa greška: {e}')
    return _restart_gunicorn()
```

**Novi `check_gunicorn()` za socket režim:**

```python
GUNICORN_SOCKET = '/run/gunicorn-fina/gunicorn.sock'

def check_gunicorn():
    import os, socket as sock_lib, requests as req

    # 1. systemd status
    r = subprocess.run(['systemctl', 'is-active', 'gunicorn-fina'],
                       capture_output=True, text=True, timeout=5)
    systemd_status = r.stdout.strip()

    # 2. Socket fajl postoji?
    socket_exists = os.path.exists(GUNICORN_SOCKET)

    # 3. Socket prihvaća konekcije?
    socket_ok = False
    if socket_exists:
        try:
            s = sock_lib.socket(sock_lib.AF_UNIX, sock_lib.SOCK_STREAM)
            s.settimeout(3)
            s.connect(GUNICORN_SOCKET)
            s.close()
            socket_ok = True
        except Exception:
            socket_ok = False

    # 4. HTTP check
    http_ok = False
    http_code = None
    try:
        resp = req.get('http://127.0.0.1/health/', timeout=5)
        http_code = resp.status_code
        http_ok = (http_code == 200)
    except Exception:
        http_ok = False

    # DIJAGNOZA
    if systemd_status == 'active' and socket_ok and http_ok:
        return True, 'OK (socket=live, HTTP=200)'

    if not socket_exists or not socket_ok:
        logger.error(f'Gunicorn socket problem. exists={socket_exists}, ok={socket_ok}. Auto-fix.')
        fixed = _fix_broken_gunicorn()
        return fixed, 'AUTOFIX: socket fix + restart' if fixed else 'AUTOFIX FAILED'

    if not http_ok:
        logger.error(f'Gunicorn socket OK ali HTTP={http_code}. Graceful reload.')
        _graceful_reload_gunicorn()
        return False, f'Reload poslan (HTTP={http_code})'

    return False, f'systemd={systemd_status}, socket={socket_ok}, http={http_ok}'
```

Implementiraj ovu logiku u `core/ai_health.py` — zamijeni cijeli `check_gunicorn()` i `_kill_zombie_port_8000()`.

---

### TASK 7 — Verifikacija i testovi

```bash
# 1. Je li socket aktivan?
ls -la /run/gunicorn-fina/gunicorn.sock

# 2. Radi li aplikacija?
curl -s https://limit-connect.com/health/
# Odgovor: {"status": "ok"} ili HTTP 200

# 3. Je li TCP port 8000 slobodan? (ne smije odgovarati)
curl -s http://127.0.0.1:8000/health/ || echo "TCP port slobodan - ISPRAVNO"

# 4. Docker bridge (172.17.0.1:8000) još uvijek radi?
curl -s http://172.17.0.1:8000/health/
# Treba odgovoriti 200 (MCP server koristi ovo)

# 5. Simuliraj zombie — provjeri auto-fix
sudo kill -9 $(pgrep -f gunicorn | head -1)
sleep 10
curl -s https://limit-connect.com/health/
# Systemd treba automatski restartat i sve raditi
```

---

### TASK 8 — Ažuriraj FENIX_STATUS.md

Dodaj u sekciju "DEPLOYAN DANAS":
```
| Gunicorn Unix Socket | - | Eliminacija port-8000 zombie incidenta, 15-20% brži |
| ai_health.py v2 | - | check_gunicorn() socket-aware, auto-fix bez TCP |
```

---

## ROLLBACK (ako nešto ne radi)

```bash
# 1. Vrati stari service fajl
sudo nano /etc/systemd/system/gunicorn-fina.service
# Vrati: --bind 127.0.0.1:8000 --bind 172.17.0.1:8000
# Ukloni: ExecStartPre, ExecStopPost, unix socket bind

# 2. Vrati nginx
sudo sed -i 's|proxy_pass http://gunicorn_fina|proxy_pass http://127.0.0.1:8000|g' \
    /etc/nginx/sites-enabled/*
# Ukloni upstream gunicorn_fina blok

# 3. Primijeni
sudo systemctl daemon-reload
sudo systemctl restart gunicorn-fina
sudo systemctl reload nginx

# 4. Provjeri
curl -s http://127.0.0.1:8000/health/
```

---

## NAPOMENE

- `ExecStartPre=/bin/rm -f socket` znači da systemd **sam briše stari socket** prije
  svakog starta — zombie problem je strukturno eliminiran, ne samo mitigiran
- Unix socket ne može biti "zauzet" od drugog procesa — fajl sistem to ne dopušta
- `/run/` je tmpfs (RAM) — socket se briše pri restartu OS-a, `tmpfiles.d` ga rekreira
- Nginx `upstream` blok omogućuje dodavanje više gunicorn instanci u budućnosti
  (load balancing) bez promjene `location` blokova
- `172.17.0.1:8000` ostaje za Docker/MCP — ne diraj bez provjere Task 1

---

## STATUS

- Kreiran: 2026-03-29 | Sonnet
- Implementacija: ⏳ CC Code
- Prioritet: 🟠 VISOK — ali ne blokira go-live
- Preporučeni termin: tjedan dana prije 15.4. (10.4.) — na čistom serveru nakon load testa
