from django.urls import path

from . import views

app_name = 'interventions'

urlpatterns = [
    path("",              views.kanban,            name="kanban"),
    path("new/",          views.new_intervention,  name="new"),
    path("<int:pk>/field/",   views.field_view,    name="field"),
    path("<int:pk>/status/",  views.update_status, name="update_status"),
    path("<int:pk>/assign/",  views.assign_worker, name="assign"),
    path("<int:pk>/escalate/",views.escalate,      name="escalate"),
    path("public/",            views.public_intervention, name="public"),
    path("sos/",               views.public_intervention, name="sos"),
    path("<int:pk>/gps/",      views.gps_update,          name="gps_update"),
]
