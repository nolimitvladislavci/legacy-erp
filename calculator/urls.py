from django.urls import path
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from . import views

app_name = 'calculator'

urlpatterns = [
    path('',                       views.public_calculator,      name='public_calculator'),
    path('salary/',                views.salary_calculator,      name='salary_calculator'),
    path('bathroom/',              views.bathroom_public,        name='bathroom_public'),
    path('bathroom/anfrage/',       views.bathroom_anfrage,       name='bathroom_anfrage'),
    path('bathroom/internal/',     views.bathroom_internal,      name='bathroom_internal'),
    path('aufnahme/',               views.aufnahme_view,          name='aufnahme'),
    path('aufnahme/save/',          views.aufnahme_save,          name='aufnahme_save'),
    path('internal/',              views.calculator_list,        name='estimate_list'),
    path('<int:calc_id>/add-item/', views.add_item,              name='add_item'),
    path('<int:pk>/pdf/',          views.export_calculation_pdf, name='estimate_pdf'),
    path('bom/',                    views.bom_list,   name='bom_list'),
    path('bom/new/',                views.bom_create, name='bom_create'),
    path('bom/<int:pk>/',           views.bom_detail, name='bom_detail'),
    path('bom/<int:pk>/edit/',      views.bom_edit,   name='bom_edit'),
    path('<int:pk>/synesis-export/', views.export_to_synesis, name='synesis_export'),
    path('<int:pk>/pkv-export/', views.export_pkv_to_synesis, name='pkv_export'),
]
