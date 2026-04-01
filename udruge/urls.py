from django.urls import path
from . import views

app_name = 'udruge'

urlpatterns = [
    # Clanovi
    path('', views.clan_list, name='clan_list'),
    path('novi/', views.clan_create, name='clan_create'),
    path('<int:pk>/', views.clan_detail, name='clan_detail'),
    path('<int:pk>/oib-lookup/', views.oib_lookup, name='oib_lookup'),
    path('<int:pk>/ai-analyze/', views.ai_analyze, name='ai_analyze'),
    path('<int:pk>/whatsapp/', views.send_whatsapp, name='send_whatsapp'),

    # Clanarine
    path('clanarine/', views.clanarina_list, name='clanarina_list'),
    path('clanarine/bulk/', views.clanarina_bulk_create, name='clanarina_bulk_create'),
    path('clanarine/<int:pk>/pay/', views.clanarina_pay, name='clanarina_pay'),

    # Donacije
    path('donacije/', views.donacija_list, name='donacija_list'),
    path('donacije/nova/', views.donacija_create, name='donacija_create'),
    path('donacije/<int:pk>/potvrda/', views.download_donatorska_potvrda, name='donatorska_potvrda'),

    # Knjiga primitaka i izdataka
    path('knjiga/', views.knjiga_primitaka, name='knjiga_primitaka'),
    path('knjiga/nova/', views.knjiga_primitaka_create, name='knjiga_primitaka_create'),

    # FINA izvjestaji
    path('izvjestaji/', views.fina_reports, name='fina_reports'),
    path('izvjestaji/pr-ras-npf/', views.download_prras_npf, name='download_prras_npf'),
    path('izvjestaji/bil-npf/', views.download_bil_npf, name='download_bil_npf'),
    path('izvjestaji/g-pr-iz-npf/', views.download_gpriznpf, name='download_gpriznpf'),

    # EU Fondovi / Volonteri
    path('eu/', views.eu_reports, name='eu_reports'),
    path('eu/timesheet/', views.download_volunteer_timesheet, name='volunteer_timesheet'),
    path('eu/inkind/', views.download_inkind_report, name='inkind_report'),
    path('eu/godisnje/', views.download_annual_volunteer_report, name='annual_volunteer_report'),

    # Dogadjaji
    path('dogadjaji/', views.dogadjaj_list, name='dogadjaj_list'),
    path('dogadjaji/novi/', views.dogadjaj_create, name='dogadjaj_create'),
    path('dogadjaji/<int:pk>/', views.dogadjaj_detail, name='dogadjaj_detail'),
    path('dogadjaji/<int:pk>/prijava/', views.dogadjaj_register, name='dogadjaj_register'),

    # Kampanje
    path('kampanje/', views.kampanja_list, name='kampanja_list'),
    path('kampanje/nova/', views.kampanja_create, name='kampanja_create'),
    path('kampanje/<int:pk>/', views.kampanja_detail, name='kampanja_detail'),

    # Email kampanje
    path('email/', views.email_kampanja_list, name='email_kampanja_list'),
    path('email/nova/', views.email_kampanja_create, name='email_kampanja_create'),
    path('email/<int:pk>/send/', views.email_kampanja_send, name='email_kampanja_send'),

    # Edit
    path('<int:pk>/edit/', views.clan_edit, name='clan_edit'),

    # Volonterske aktivnosti
    path('volonteri/', views.volunteer_list, name='volunteer_list'),
    path('volonteri/nova/', views.volunteer_create, name='volunteer_create'),

    # EU fond AI search
    path('eu/ai-search/', views.eu_fund_search, name='eu_fund_search'),

    # Sekcije
    path('sekcije/', views.sekcija_list, name='sekcija_list'),
    path('sekcije/nova/', views.sekcija_create, name='sekcija_create'),
    path('sekcije/<int:pk>/', views.sekcija_detail, name='sekcija_detail'),
    path('sekcije/<int:pk>/add-member/', views.sekcija_add_member, name='sekcija_add_member'),
    # Dokumenti / Dozvole
    path('<int:pk>/dokumenti/', views.clan_dokumenti, name='clan_dokumenti'),
    path('dozvole/', views.dozvole_pregled, name='dozvole_pregled'),

    # ═══════════════════════════════════════════════════════════════════
    # DVD — DOBROVOLJNO VATROGASNO DRUŠTVO
    # ═══════════════════════════════════════════════════════════════════
    path('dvd/oprema/', views.vatrogasna_oprema_list, name='vatrogasna_oprema_list'),
    path('dvd/oprema/nova/', views.vatrogasna_oprema_create, name='vatrogasna_oprema_create'),
    path('dvd/oprema/<int:pk>/', views.vatrogasna_oprema_detail, name='vatrogasna_oprema_detail'),
    path('dvd/oprema/<int:pk>/edit/', views.vatrogasna_oprema_edit, name='vatrogasna_oprema_edit'),
    path('dvd/vozila/', views.vatrogasno_vozilo_list, name='vatrogasno_vozilo_list'),
    path('dvd/vozila/novo/', views.vatrogasno_vozilo_create, name='vatrogasno_vozilo_create'),
    path('dvd/intervencije/', views.intervencija_list, name='intervencija_list'),
    path('dvd/intervencije/nova/', views.intervencija_create, name='intervencija_create'),
    path('dvd/intervencije/<int:pk>/', views.intervencija_detail, name='intervencija_detail'),
    path('dvd/intervencije/<int:pk>/edit/', views.intervencija_edit, name='intervencija_edit'),
    path('dvd/vjezbe/', views.vjezba_list, name='vjezba_list'),
    path('dvd/vjezbe/nova/', views.vjezba_create, name='vjezba_create'),
    path('dvd/zvanja/', views.vatrogasno_zvanje_list, name='vatrogasno_zvanje_list'),

    # ═══════════════════════════════════════════════════════════════════
    # KUD — KULTURNO-UMJETNIČKO DRUŠTVO
    # ═══════════════════════════════════════════════════════════════════
    path('kud/repertoar/', views.repertoar_list, name='repertoar_list'),
    path('kud/repertoar/novi/', views.repertoar_create, name='repertoar_create'),
    path('kud/probe/', views.proba_list, name='proba_list'),
    path('kud/probe/nova/', views.proba_create, name='proba_create'),
    path('kud/kostimi/', views.kostim_list, name='kostim_list'),
    path('kud/kostimi/novi/', views.kostim_create, name='kostim_create'),
    path('kud/kostimi/<int:pk>/', views.kostim_detail, name='kostim_detail'),
    path('kud/kostimi/<int:pk>/edit/', views.kostim_edit, name='kostim_edit'),
    path('kud/nastup-plan/', views.nastup_plan_list, name='nastup_plan_list'),

    # ═══════════════════════════════════════════════════════════════════
    # RIBARI — ŠPORTSKI RIBOLOV
    # ═══════════════════════════════════════════════════════════════════
    path('ribari/reviri/', views.revir_list, name='revir_list'),
    path('ribari/reviri/novi/', views.revir_create, name='revir_create'),
    path('ribari/reviri/<int:pk>/', views.revir_detail, name='revir_detail'),
    path('ribari/dozvole/', views.ribolovna_dozvola_list, name='ribolovna_dozvola_list'),
    path('ribari/dozvole/nova/', views.ribolovna_dozvola_create, name='ribolovna_dozvola_create'),
    path('ribari/ulovi/', views.ulov_list, name='ulov_list'),
    path('ribari/ulovi/novi/', views.ulov_create, name='ulov_create'),
    path('ribari/poribljavanje/', views.poribljavanje_list, name='poribljavanje_list'),
    path('ribari/poribljavanje/novo/', views.poribljavanje_create, name='poribljavanje_create'),
    path('ribari/cuvari/', views.cuvarska_straza_list, name='cuvarska_straza_list'),
    path('ribari/cuvari/nova/', views.cuvarska_straza_create, name='cuvarska_straza_create'),

    # ═══════════════════════════════════════════════════════════════════
    # PČELARI — PČELARSKA DRUŠTVA
    # ═══════════════════════════════════════════════════════════════════
    path('pcelari/pcelinjaci/', views.pcelinjak_list, name='pcelinjak_list'),
    path('pcelari/pcelinjaci/novi/', views.pcelinjak_create, name='pcelinjak_create'),
    path('pcelari/pcelinjaci/<int:pk>/', views.pcelinjak_detail, name='pcelinjak_detail'),
    path('pcelari/kosnice/', views.kosnica_list, name='kosnica_list'),
    path('pcelari/kosnice/nova/', views.kosnica_create, name='kosnica_create'),
    path('pcelari/tretmani-pcele/', views.tretman_kosnice_list, name='tretman_kosnice_list'),
    path('pcelari/tretmani-pcele/novi/', views.tretman_kosnice_create, name='tretman_kosnice_create'),
    path('pcelari/med/', views.med_proizvodnja_list, name='med_proizvodnja_list'),
    path('pcelari/med/nova/', views.med_proizvodnja_create, name='med_proizvodnja_create'),
    path('pcelari/selidbe/', views.selidba_list, name='selidba_list'),
    path('pcelari/selidbe/nova/', views.selidba_create, name='selidba_create'),

    # ═══════════════════════════════════════════════════════════════════
    # RAKIJA — PROIZVOĐAČI RAKIJE
    # ═══════════════════════════════════════════════════════════════════
    path('rakija/kotlovi/', views.destilacija_kotao_list, name='kotao_list'),
    path('rakija/kotlovi/novi/', views.destilacija_kotao_create, name='kotao_create'),
    path('rakija/destilacije/', views.destilacija_log_list, name='destilacija_list'),
    path('rakija/destilacije/nova/', views.destilacija_log_create, name='destilacija_create'),
    path('rakija/rakije/', views.rakija_proizvodnja_list, name='rakija_list'),
    path('rakija/rakije/nova/', views.rakija_proizvodnja_create, name='rakija_create'),
    path('rakija/trosarina/', views.trosarina_list, name='trosarina_list'),
    path('rakija/trosarina/nova/', views.trosarina_create, name='trosarina_create'),

    # ═══════════════════════════════════════════════════════════════════
    # VOĆARI — VOĆARSKA UDRUŽENJA
    # ═══════════════════════════════════════════════════════════════════
    path('vocari/vocnjaci/', views.vocnjak_list, name='vocnjak_list'),
    path('vocari/vocnjaci/novi/', views.vocnjak_create, name='vocnjak_create'),
    path('vocari/vocnjaci/<int:pk>/', views.vocnjak_detail, name='vocnjak_detail'),
    path('vocari/berbe/', views.berba_list, name='berba_list'),
    path('vocari/berbe/nova/', views.berba_create, name='berba_create'),
    path('vocari/tretmani-vocnjak/', views.tretman_vocnjaka_list, name='tretman_vocnjaka_list'),
    path('vocari/tretmani-vocnjak/novi/', views.tretman_vocnjaka_create, name='tretman_vocnjaka_create'),

    # ═══════════════════════════════════════════════════════════════════
    # BRANITELJI
    # ═══════════════════════════════════════════════════════════════════
    path('branitelji/', views.branitelji_dashboard, name='branitelji_dashboard'),
    path('branitelji/status/<int:clan_pk>/create/', views.branitelj_status_create, name='branitelj_status_create'),

    # ═══════════════════════════════════════════════════════════════════
    # LOV — LOVAČKA DRUŠTVA
    # ═══════════════════════════════════════════════════════════════════
    path('lov/', views.lov_dashboard, name='lov_dashboard'),
    path('lov/iskaznice/', views.lov_iskaznice_list, name='lov_iskaznice_list'),
    path('lov/dopustenja/', views.lov_dopustenja_list, name='lov_dopustenja_list'),
    path('lov/dopustenja/create/', views.lov_dopustenje_create, name='lov_dopustenje_create'),
    path('lov/zapisnici/', views.lov_zapisnici_list, name='lov_zapisnici_list'),
    path('lov/zapisnici/create/', views.lov_zapisnik_create, name='lov_zapisnik_create'),
    path('lov/trofeji/', views.lov_trofeji_list, name='lov_trofeji_list'),

    # Edit views — branitelji + lov
    path('branitelji/status/<int:pk>/edit/', views.branitelj_status_edit, name='branitelj_status_edit'),
    path('lov/lovista/', views.loviste_list, name='loviste_list'),
    path('lov/lovista/create/', views.loviste_create, name='loviste_create'),
    path('lov/lovista/<int:pk>/edit/', views.loviste_edit, name='loviste_edit'),
    path('lov/dopustenja/<int:pk>/edit/', views.lov_dopustenje_edit, name='lov_dopustenje_edit'),
    path('lov/zapisnici/<int:pk>/edit/', views.lov_zapisnik_edit, name='lov_zapisnik_edit'),
    path('lov/trofeji/create/', views.trofej_create, name='trofej_create'),

    # ZADRUGE
    path('zadruge/', views.zadruge_dashboard, name='zadruge_dashboard'),
    path('zadruge/novi/', views.zadrugar_create, name='zadrugar_create'),
    path('zadruge/revizija/', views.revizija_create, name='revizija_create'),

    # ═══════════════════════════════════════════════════════════════════
    # GOLUBAR — GOLUBARSKI SAVEZ / UTRKE
    # ═══════════════════════════════════════════════════════════════════
    path('golubar/', views.golubar_dashboard, name='golubar_dashboard'),
    path('golubar/golubinjaci/', views.golubinjak_list, name='golubinjak_list'),
    path('golubar/golubinjaci/novi/', views.golubinjak_create, name='golubinjak_create'),
    path('golubar/golubinjaci/<int:pk>/', views.golubinjak_detail, name='golubinjak_detail'),
    path('golubar/golubovi/', views.golub_list, name='golub_list'),
    path('golubar/golubovi/novi/', views.golub_create, name='golub_create'),
    path('golubar/golubovi/<int:pk>/', views.golub_detail, name='golub_detail'),
    path('golubar/golubovi/<int:pk>/edit/', views.golub_edit, name='golub_edit'),
    path('golubar/golubovi/<int:pk>/seal/', views.golub_seal, name='golub_seal'),
    path('golubar/parovi/', views.par_list, name='par_list'),
    path('golubar/parovi/novi/', views.par_create, name='par_create'),
    path('golubar/parovi/<int:par_pk>/leglo/', views.leglo_create, name='leglo_create'),
    path('golubar/golubovi/<int:golub_pk>/zdravstveni/', views.zdravstveni_create, name='zdravstveni_create'),
    path('golubar/utrke/', views.utrka_list, name='utrka_list'),
    path('golubar/utrke/nova/', views.utrka_create, name='utrka_create'),
    path('golubar/utrke/<int:pk>/', views.utrka_detail, name='utrka_detail'),
    path('golubar/utrke/<int:utrka_pk>/rezultat/', views.rezultat_create, name='rezultat_create'),
    path('golubar/ai-ime/', views.golubar_ai_ime, name='golubar_ai_ime'),
    path('golubar/ai-prsten/', views.golubar_ai_prsten, name='golubar_ai_prsten'),

    # ═══════════════════════════════════════════════════════════════════
    # PERAD — JATA (Flock)
    # ═══════════════════════════════════════════════════════════════════
    path('perad/', views.flock_list, name='flock_list'),
    path('perad/novo/', views.flock_create, name='flock_create'),
    path('perad/<int:pk>/', views.flock_detail, name='flock_detail'),
    path('perad/<int:pk>/edit/', views.flock_edit, name='flock_edit'),
    path('perad/<int:flock_pk>/jaja/', views.egg_record_create, name='egg_record_create'),
    path('perad/<int:flock_pk>/zdravstveni/', views.flock_health_create, name='flock_health_create'),
    path('perad/<int:flock_pk>/uginuce/', views.flock_mortality_create, name='flock_mortality_create'),

    # Burza Bridge — "Ponudi na tržnicu"
    path('bridge/publish/', views.bridge_publish, name='bridge_publish'),

    # Glazbena škola
    path('glazbena-skola/', views.glazbena_skola_dashboard, name='glazbena_skola_dashboard'),
    path('glazbena-skola/fakturiraj/', views.glazbena_skola_fakturiraj, name='glazbena_fakturiraj'),
]
