"""
KORAK 8 — Load Test
Flow: login → dashboard → invoice list → company switch
50 VU, 10 min, P95 < 3s, 0 x 5xx

Pokreni:
  cd /var/www/fina-connect
  venv/bin/locust -f load_tests/locustfile.py \
    --headless -u 50 -r 5 -t 10m \
    --csv=load_tests/results/report \
    --html=load_tests/results/report.html
"""

import random

from locust import HttpUser, between, task

TEST_EMAIL = "loadtest@limit-connect.com"
TEST_PASS = "LoadTest2026!"
MEMBERSHIP_IDS = [223, 224]  # Viskovic Bau, Sa-Ni Mont

# Proxy headeri — gunicorn prima HTTPS zahtjeve kroz nginx reverse proxy
PROXY_HEADERS = {
    "X-Forwarded-Proto": "https",
    "X-Forwarded-Host": "limit-connect.com",
}


class FenixUser(HttpUser):
    """
    Simulira računovođu:
    1. Login (email + password)
    2. Dashboard
    3. Lista faktura
    4. Company switch
    5. Arhiva, novi račun (sporije)
    """

    wait_time = between(1, 3)
    host = "http://127.0.0.1:8000"

    def on_start(self):
        """Login pri startu svake VU sesije."""
        # Dodaj proxy headere u sve zahtjeve ove sesije
        self.client.headers.update(PROXY_HEADERS)
        self._login()

    def _login(self):
        """GET login page → uzmi CSRF → POST credentials."""
        self.client.get(
            "/hr/login/",
            name="/hr/login/ [GET]",
            allow_redirects=True,
        )
        csrf = self.client.cookies.get("csrftoken", "")

        with self.client.post(
            "/hr/login/",
            data={
                "email": TEST_EMAIL,
                "password": TEST_PASS,
                "csrfmiddlewaretoken": csrf,
            },
            headers={"Referer": "http://127.0.0.1:8000/hr/login/"},
            name="/hr/login/ [POST]",
            allow_redirects=True,
            catch_response=True,
        ) as r:
            # Ako je redirect na login (failed auth) → failure
            if "login" in r.url and r.status_code < 400:
                # Provjerimo ima li error u sadržaju
                if b"Pogresna lozinka" in r.content or b"Ne postoji" in r.content:
                    r.failure("Login failed — auth error")
            elif r.status_code >= 500:
                r.failure(f"Login 5xx: {r.status_code}")

    @task(5)
    def dashboard(self):
        """Dashboard — najčešći task."""
        with self.client.get(
            "/hr/dashboard/",
            name="/hr/dashboard/",
            allow_redirects=True,
            catch_response=True,
        ) as r:
            if r.status_code >= 500:
                r.failure(f"Dashboard 5xx: {r.status_code}")
            elif r.status_code == 200 and b"login" in r.url.encode():
                r.failure("Dashboard redirected to login — session lost")

    @task(4)
    def invoice_list(self):
        """Lista faktura."""
        with self.client.get(
            "/hr/invoicing/",
            name="/hr/invoicing/",
            allow_redirects=True,
            catch_response=True,
        ) as r:
            if r.status_code >= 500:
                r.failure(f"Invoice list 5xx: {r.status_code}")

    @task(3)
    def arhiva(self):
        """Digitalna arhiva."""
        with self.client.get(
            "/hr/documents/arhiva/",
            name="/hr/documents/arhiva/",
            allow_redirects=True,
            catch_response=True,
        ) as r:
            if r.status_code >= 500:
                r.failure(f"Arhiva 5xx: {r.status_code}")

    @task(2)
    def switch_company(self):
        """Company switch — kritični flow."""
        membership_id = random.choice(MEMBERSHIP_IDS)
        csrf = self.client.cookies.get("csrftoken", "")
        with self.client.post(
            "/hr/accounts/switch-company/",
            data={
                "membership_id": membership_id,
                "csrfmiddlewaretoken": csrf,
            },
            headers={"Referer": "http://127.0.0.1:8000/hr/dashboard/"},
            name="/hr/accounts/switch-company/ [POST]",
            allow_redirects=True,
            catch_response=True,
        ) as r:
            if r.status_code >= 500:
                r.failure(f"Switch company 5xx: {r.status_code}")

    @task(1)
    def invoice_new_form(self):
        """Nova faktura — GET forma."""
        with self.client.get(
            "/hr/invoicing/new/",
            name="/hr/invoicing/new/",
            allow_redirects=True,
            catch_response=True,
        ) as r:
            if r.status_code >= 500:
                r.failure(f"Invoice new 5xx: {r.status_code}")
