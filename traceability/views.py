from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist


@login_required
def index(request):
    return render(request, "coming_soon.html", {
        "module_name": "Sljedivost",
        "module_icon": "fas fa-qrcode",
        "module_description": "Pracenje podrijetla proizvoda od polja do stola — QR kodovi, LOT brojevi i HACCP evidencija.",
    })
