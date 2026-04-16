from django.urls import path

from no_limit import views

app_name = "no_limit"

urlpatterns = [
    # Landing
    path("", views.landing, name="no_limit_home"),
    # Info stranice
    path("o-nama/", views.o_nama, name="o_nama"),
    path("statut/", views.statut, name="statut"),
    path("statut/pdf/", views.statut_pdf, name="statut_pdf"),
    path("projekti/", views.projekti, name="projekti"),
    path("partneri/", views.partneri, name="partneri"),
    path("kontakt/", views.kontakt, name="kontakt"),
    # Ambasadori
    path("ambasadori/", views.ambasadori, name="ambasadori"),
    path("ambasadori/prijava/", views.ambasador_prijava, name="ambasador_prijava"),
    path("ambasadori/hvala/", views.ambasador_hvala, name="ambasador_hvala"),
    # Dokumenti PDF
    path("dokumenti/ambasadorski-ugovor.pdf", views.ambasador_ugovor_pdf, name="ambasador_ugovor_pdf"),
    # Staro (backward compat)
    path("preuzmi-vodic/", views.preuzmi_vodic, name="preuzmi_vodic"),
    path("vodic/", views.vodic_online, name="vodic_online"),
    path("azili/prijava/", views.prijava_azila, name="prijava_azila"),
]
