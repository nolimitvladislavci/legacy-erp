"""
KORAK 8 — Load Test: 50 VU, 10 min, P95 < 3s, 0 x 5xx
Flow: login → invoicing → arhiva → smart-import → switch company

Pokreni:
  cd /var/www/fina-connect
  venv/bin/locust -f load_tests/locustfile.py \
    --headless -u 50 -r 5 -t 10m \
    --csv=load_tests/results/report \
    --html=load_tests/results/report.html \
    --host=https://limit-connect.com
"""

import re
from locust import HttpUser, task, between


TEST_EMAIL = "loadtest@limit-connect.com"
TEST_PASS = "LoadTest2026!"
MEMBERSHIP_ID = 223  # Viskovic Bau (admin, TC signed)


class FenixUser(HttpUser):
    """
    Simulira računovođu kroz produkcijski stack (nginx + SSL + gunicorn + Django).
    Testira: login, invoice list, digitalna arhiva, AI import, company switch.
    """

    wait_time = between(1, 3)
    host = "https://limit-connect.com"

    def on_start(self):
        self._login()

    def _get_csrf(self, html: str) -> str:
        m = re.search(r'name="csrfmiddlewaretoken".*?value="([^"]+)"', html)
        return m.group(1) if m else self.client.cookies.get("csrftoken", "")

    def _login(self):
        """Login: GET form + POST credentials. Ne prati redirect (zaobilazi redirect loop na dashboard)."""
        with self.client.get(
            "/hr/login/",
            name="/hr/login/ [GET]",
            allow_redirects=True,
            catch_response=True,
        ) as r:
            if r.status_code >= 500:
                r.failure(f"Login GET 5xx: {r.status_code}")
                return
            csrf = self._get_csrf(r.text)

        with self.client.post(
            "/hr/login/",
            data={
                "email": TEST_EMAIL,
                "password": TEST_PASS,
                "csrfmiddlewaretoken": csrf,
            },
            headers={"Referer": "https://limit-connect.com/hr/login/"},
            name="/hr/login/ [POST]",
            allow_redirects=False,  # Zaobilazi redirect loop: /hr/dashboard/ → /hr/dashboard/company/ → ...
            catch_response=True,
        ) as r:
            if r.status_code in [302, 301]:
                r.success()  # Redirect = uspješan login
            elif r.status_code >= 500:
                r.failure(f"Login POST 5xx: {r.status_code}")
            elif b"Pogresna lozinka" in r.content or b"Ne postoji" in r.content:
                r.failure("Login auth error")
            elif r.status_code == 200 and b"login" in r.url.encode():
                r.failure("Login returned to login page")

    @task(5)
    def invoice_list(self):
        """Lista faktura — kritični read-heavy endpoint."""
        with self.client.get(
            "/hr/invoicing/",
            name="/hr/invoicing/",
            allow_redirects=True,
            catch_response=True,
        ) as r:
            if r.status_code >= 500:
                r.failure(f"Invoice list 5xx: {r.status_code}")
            elif r.status_code == 200 and "login" in r.url:
                r.success()
                self._login()

    @task(4)
    def arhiva(self):
        """Digitalna arhiva dokumenta."""
        with self.client.get(
            "/hr/documents/arhiva/",
            name="/hr/documents/arhiva/",
            allow_redirects=True,
            catch_response=True,
        ) as r:
            if r.status_code >= 500:
                r.failure(f"Arhiva 5xx: {r.status_code}")
            elif r.status_code == 200 and "login" in r.url:
                r.success()
                self._login()

    @task(2)
    def smart_import(self):
        """AI import stranica."""
        with self.client.get(
            "/hr/smart-import/",
            name="/hr/smart-import/",
            allow_redirects=True,
            catch_response=True,
        ) as r:
            if r.status_code >= 500:
                r.failure(f"Smart import 5xx: {r.status_code}")
            elif r.status_code == 200 and "login" in r.url:
                r.success()
                self._login()

    @task(2)
    def switch_company(self):
        """Company switch — POST, provjeri 302 (ne prati redirect)."""
        csrf = self.client.cookies.get("csrftoken", "")
        if not csrf:
            return
        with self.client.post(
            "/hr/accounts/switch-company/",
            data={
                "membership_id": MEMBERSHIP_ID,
                "csrfmiddlewaretoken": csrf,
            },
            headers={"Referer": "https://limit-connect.com/hr/invoicing/"},
            name="/hr/accounts/switch-company/ [POST]",
            allow_redirects=False,  # 302 je uspjeh
            catch_response=True,
        ) as r:
            if r.status_code in [302, 301, 200]:
                r.success()
            elif r.status_code >= 500:
                r.failure(f"Switch company 5xx: {r.status_code}")
            else:
                r.failure(f"Switch company unexpected: {r.status_code}")

    @task(1)
    def invoice_arhiva_upload_form(self):
        """Upload forma arhive — GET."""
        with self.client.get(
            "/hr/documents/arhiva/upload/",
            name="/hr/documents/arhiva/upload/",
            allow_redirects=True,
            catch_response=True,
        ) as r:
            if r.status_code >= 500:
                r.failure(f"Upload form 5xx: {r.status_code}")
            elif r.status_code == 200 and "login" in r.url:
                r.success()
                self._login()
