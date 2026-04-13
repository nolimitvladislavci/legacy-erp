from django.urls import path

from . import views

app_name = "burza"

urlpatterns = [
    path("", views.kanban_board, name="kanban"),
    path("lead/new/", views.lead_new, name="lead_new"),
    path("lead/<int:pk>/", views.lead_detail, name="lead_detail"),
    path("lead/<int:pk>/move/", views.lead_move, name="lead_move"),
    path("lead/<int:pk>/preuzmi/", views.lead_preuzmi, name="lead_preuzmi"),
    path("lead/<int:pk>/invoice/", views.create_invoice_from_lead, name="invoice_from_lead"),
    path("lead/<int:lead_pk>/bathroom/", views.bathroom_to_project, name="bathroom_to_project"),
    path("lead/<int:pk>/bathroom-pdf/", views.bathroom_pdf, name="bathroom_pdf"),
    path("kanban/col/<str:status>/", views.kanban_col, name="kanban_col"),
    path("upit/", views.public_upit, name="upit"),
    path("upit/hvala/", views.upit_hvala, name="upit_hvala"),
]
