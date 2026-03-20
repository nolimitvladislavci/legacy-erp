from django.urls import path

from . import views

app_name = 'assessment'

urlpatterns = [
    path('',                             views.assessment_list,           name='list'),
    path('new/',                         views.assessment_new,            name='new'),
    path('save/',                        views.assessment_save,           name='save'),
    path('<int:pk>/',                    views.assessment_detail,         name='detail'),
    path('<int:pk>/pdf/',                views.assessment_pdf,            name='pdf'),
    path('<int:pk>/photos/',             views.assessment_upload_photo,   name='upload_photo'),
    path('<int:pk>/photos/<int:photo_pk>/delete/', views.assessment_delete_photo, name='delete_photo'),
    path('<int:pk>/status/', views.assessment_status_update, name='status_update'),
    path('bad-nalaz/', views.bad_nalaz_new, name='bad_nalaz'),
]
