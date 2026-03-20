from django.urls import path
from . import views

app_name = "ai_assistant"

urlpatterns = [
    path('api/patrol-insights/', views.patrol_insights_api, name='patrol_insights_api'),
    path('api/context-widget/', views.ai_context_widget, name='ai_context_widget'),
    path('intro/', views.ai_intro, name='ai_intro'),
    path("", views.chat_page, name="chat_page"),
    path("api/chat/", views.chat_api, name="chat_api"),
    path("api/widget/", views.chat_widget_data, name="chat_widget_data"),
    path("patrol/", views.patrol_page, name="patrol"),
    path("api/analyze-image/", views.analyze_image, name="analyze_image"),
]
