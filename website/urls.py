from django.urls import path

from . import cms_views, views

app_name = "website"

urlpatterns = [
    path("grosmarkt/anfrage/", views.grosmarkt_anfrage, name="grosmarkt_anfrage"),
    # Viskovic CMS gallery (legacy)
    path("cms/gallery/", cms_views.cms_gallery, name="cms_gallery"),
    path("cms/gallery/toggle/<int:id>/", cms_views.toggle_img, name="toggle_img"),
    # Viskovic public pages
    path("feedback/", views.feedback_page, name="feedback"),
    path("", views.homepage, name="homepage"),
    path("bau/", views.bau_page, name="bau_page"),
    path("admin-panel/", views.admin_panel, name="admin_panel"),
    path("hitna-intervencija/", views.hitna_intervencija, name="hitna_intervencija"),
    path("hitna-intervencija/hvala/", views.hitna_hvala, name="hitna_hvala"),
    path("video-galerija/", views.video_galerija, name="video_galerija"),
    path("hr/", views.viskovic_hr, name="viskovic_hr"),
    # Website builder CMS
    path("editor/", cms_views.website_editor, name="website_editor"),
    path("editor/service/save/", cms_views.website_service_save, name="website_service_save"),
    path("editor/service/<int:pk>/delete/", cms_views.website_service_delete, name="website_service_delete"),
    path("editor/gallery/upload/", cms_views.website_gallery_upload, name="website_gallery_upload"),
    path("editor/gallery/<int:pk>/delete/", cms_views.website_gallery_delete, name="website_gallery_delete"),
    path("editor/review/save/", cms_views.website_review_save, name="website_review_save"),
    path("editor/messages/", cms_views.website_messages, name="website_messages"),
    # Company gallery (multi-tenant)
    path("gallery/", views.gallery_manage, name="gallery_manage"),
    path("gallery/upload/", views.gallery_upload, name="gallery_upload"),
    path("gallery/<int:pk>/delete/", views.gallery_delete, name="gallery_delete"),
]
