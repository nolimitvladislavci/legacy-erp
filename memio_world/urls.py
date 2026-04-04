from django.urls import path
from . import views

app_name = 'memio_world'

urlpatterns = [
    path('waitlist/', views.waitlist_signup, name='waitlist_signup'),
    path('waitlist/count/', views.waitlist_count, name='waitlist_count'),
]
