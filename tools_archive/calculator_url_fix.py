import os

def fix_urls():
    # 1. USKLAĐIVANJE URLS.PY SA POSTOJEĆIM VIEWS-IMA
    path = 'calculator/urls.py'
    content = """from django.urls import path
from . import views

urlpatterns = [
    # Putanja za kreiranje kalkulacije iz projekta
    path('create/<int:project_id>/', views.create_from_project, name='create_calculation'),
    # Detalji kalkulacije
    path('<int:pk>/', views.calculation_detail, name='calculation_detail'),
]
"""
    with open(path, 'w') as f:
        f.write(content)
    print("Calculator URLs synchronized with Views.")

if __name__ == "__main__":
    fix_urls()
