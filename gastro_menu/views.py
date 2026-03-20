from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def index(request):
    return render(request, "coming_soon.html", {
        "module_name": "Gastro Menu",
        "module_icon": "fas fa-utensils",
        "module_description": "Digitalni jelovnik za restorane — QR narudzba za goste, kuhinjski zaslon i upravljanje kategorijama.",
    })
