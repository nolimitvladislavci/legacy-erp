from django.urls import path

from . import views

app_name = "experiences"

urlpatterns = [
    # Iskustva / Aktivnosti
    path("", views.experience_list, name="experience_list"),
    path("novo/", views.experience_create, name="experience_create"),
    path("<int:pk>/", views.experience_detail, name="experience_detail"),
    path("<int:pk>/edit/", views.experience_edit, name="experience_edit"),
    path("<int:pk>/normativ/", views.normativ_preview, name="normativ_preview"),
    path("<int:pk>/schedule/", views.schedule_create, name="schedule_create"),
    path("schedule/<int:schedule_pk>/book/", views.booking_create, name="booking_create"),
    path("booking/<int:pk>/confirm/", views.booking_confirm_deposit, name="booking_confirm_deposit"),
    path("booking/<int:pk>/cancel/", views.booking_cancel, name="booking_cancel"),
    path("booking/<int:pk>/check-in/", views.booking_check_in, name="booking_check_in"),
    path("booking/<int:pk>/complete/", views.booking_complete, name="booking_complete"),
    path("booking/<int:pk>/no-show/", views.booking_no_show, name="booking_no_show"),
    path("booking/<int:pk>/review/", views.review_create, name="review_create"),
    # Agro Paketi
    path("paketi/", views.package_list, name="package_list"),
    path("paketi/novi/", views.package_create, name="package_create"),
    path("paketi/<int:pk>/", views.package_detail, name="package_detail"),
    path("paketi/<int:pk>/tax-breakdown/", views.package_tax_breakdown, name="package_tax_breakdown"),
    # Recall — HACCP
    path("recall/", views.recall_list, name="recall_list"),
    path("recall/novi/", views.recall_create, name="recall_create"),
    path("recall/<int:pk>/", views.recall_detail, name="recall_detail"),
    path("recall/<int:pk>/trace/", views.recall_trace, name="recall_trace"),
    path("recall/<int:pk>/notify/", views.recall_notify, name="recall_notify"),
]
