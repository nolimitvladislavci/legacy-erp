"""Test: Blagajnički izvještaj"""
from django.test import RequestFactory
from django.contrib.auth.models import User
from unittest.mock import patch
from companies.models import Company
import json

su = User.objects.get(username="superadmin")
konjik = Company.objects.get(name__icontains="Konjik")

factory = RequestFactory()
req = factory.get("/pos/session/9/cashier-report/?format=json")
req.user = su

from pos.views import cashier_full_report
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
with patch("pos.views.get_user_company", return_value=konjik):
    resp = cashier_full_report(req, 9)

data = json.loads(resp.content)
print("OK:", data.get("ok"))

print("\nPLACANJA:")
for m, d in data.get("payment_breakdown", {}).items():
    print(f"  {m}: {d['count']} transakcija, {d['total']} EUR")

print("\nPDV:")
for r, d in data.get("tax_breakdown", {}).items():
    print(f"  {r}: base={d['base']} tax={d['tax']} total={d['total']}")

print("\nBLAGAJNICI:")
for n, d in data.get("cashier_breakdown", {}).items():
    print(f"  {n}: {d['count']} rac, total={d['total']}")

print("\nGOTOVINA:")
for k, v in data.get("cash", {}).items():
    print(f"  {k}: {v}")

print("\nNAPOJNICE:", data.get("total_tips"))

print("\nAI KONTROLA:")
for w in data.get("ai_warnings", []):
    print(f"  [{w['level']}] {w['message']}")

# Validate
assert data["ok"] == True, "Report not OK"
assert len(data["payment_breakdown"]) > 0, "No payments"
assert len(data["tax_breakdown"]) > 0, "No tax"
assert len(data["cashier_breakdown"]) > 0, "No cashiers"
assert len(data["ai_warnings"]) > 0, "No AI warnings"
print("\n=== ALL ASSERTIONS PASSED ===")
