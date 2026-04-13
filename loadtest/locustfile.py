"""
LIMIT Connect — Load Test (150 concurrent users)
Usage: locust -f locustfile.py --headless -u 150 -r 10 -t 5m --host http://127.0.0.1:8000
"""
import random
import re

from locust import HttpUser, between, task


class DashboardUser(HttpUser):
    weight = 40
    wait_time = between(2, 8)

    def on_start(self):
        resp = self.client.get("/accounts/login/", name="/login [GET]")
        csrf = _extract_csrf(resp.text)
        if csrf:
            self.client.post("/accounts/login/", {
                "username": "superadmin",
                "password": "Viskovic2026",
                "csrfmiddlewaretoken": csrf,
            }, name="/login [POST]", headers={"Referer": self.host + "/accounts/login/"})

    @task(5)
    def view_dashboard(self):
        self.client.get("/hr/dashboard/", name="/dashboard")

    @task(3)
    def view_invoices(self):
        self.client.get("/hr/invoicing/", name="/invoicing/list")

    @task(2)
    def view_partners(self):
        self.client.get("/hr/partners/", name="/partners/list")

    @task(2)
    def view_work_orders(self):
        self.client.get("/hr/work-orders/", name="/work-orders/list")

    @task(1)
    def view_worktime(self):
        self.client.get("/hr/worktime/", name="/worktime")

    @task(1)
    def view_inventory(self):
        self.client.get("/hr/inventory/", name="/inventory")


class InvoiceUser(HttpUser):
    weight = 25
    wait_time = between(3, 10)

    def on_start(self):
        resp = self.client.get("/accounts/login/", name="/login [GET]")
        csrf = _extract_csrf(resp.text)
        if csrf:
            self.client.post("/accounts/login/", {
                "username": "superadmin",
                "password": "Viskovic2026",
                "csrfmiddlewaretoken": csrf,
            }, name="/login [POST]", headers={"Referer": self.host + "/accounts/login/"})

    @task(4)
    def browse_invoices(self):
        self.client.get("/hr/invoicing/", name="/invoicing/list")

    @task(3)
    def view_invoice_canvas(self):
        self.client.get("/invoicing/canvas/", name="/invoicing/canvas")

    @task(2)
    def view_pos_dashboard(self):
        self.client.get("/hr/pos/", name="/pos/dashboard")

    @task(1)
    def view_experiences(self):
        self.client.get("/hr/experiences/", name="/experiences/list")


class POSUser(HttpUser):
    weight = 20
    wait_time = between(1, 5)

    def on_start(self):
        resp = self.client.get("/accounts/login/", name="/login [GET]")
        csrf = _extract_csrf(resp.text)
        if csrf:
            self.client.post("/accounts/login/", {
                "username": "superadmin",
                "password": "Viskovic2026",
                "csrfmiddlewaretoken": csrf,
            }, name="/login [POST]", headers={"Referer": self.host + "/accounts/login/"})

    @task(5)
    def pos_terminal(self):
        self.client.get("/pos/joker/", name="/pos/joker")

    @task(3)
    def pos_dashboard(self):
        self.client.get("/hr/pos/", name="/pos/dashboard")

    @task(2)
    def board_version(self):
        self.client.get("/api/card/version/?since=2026-03-28T00:00:00Z",
                        name="/api/card/version")


class BORGUser(HttpUser):
    weight = 10
    wait_time = between(5, 15)

    def on_start(self):
        resp = self.client.get("/accounts/login/", name="/login [GET]")
        csrf = _extract_csrf(resp.text)
        if csrf:
            self.client.post("/accounts/login/", {
                "username": "superadmin",
                "password": "Viskovic2026",
                "csrfmiddlewaretoken": csrf,
            }, name="/login [POST]", headers={"Referer": self.host + "/accounts/login/"})

    @task(4)
    def borg_hub(self):
        self.client.get("/hub/", name="/borg/hub")

    @task(3)
    def operations_dashboard(self):
        self.client.get("/dashboard/operations/", name="/ops-dashboard")

    @task(1)
    def burza(self):
        self.client.get("/burza/", name="/burza")


class AnonymousUser(HttpUser):
    weight = 5
    wait_time = between(3, 12)

    @task(3)
    def view_landing(self):
        self.client.get("/", name="/ [landing]")

    @task(2)
    def view_register_step1(self):
        self.client.get("/hr/register/", name="/register/step1")

    @task(2)
    def view_validator_brochure(self):
        self.client.get("/validator/", name="/validator [brochure]")

    @task(1)
    def oib_lookup(self):
        oib = "".join([str(random.randint(0, 9)) for _ in range(11)])
        self.client.get(f"/hr/register/api/oib-lookup/?oib={oib}&country=HR",
                        name="/api/oib-lookup")


def _extract_csrf(html):
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html or "")
    return match.group(1) if match else None
