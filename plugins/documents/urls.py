from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DocumentViewSet, FolderViewSet


router = DefaultRouter()
router.register("folders", FolderViewSet, basename="documents-folder")
router.register("documents", DocumentViewSet, basename="documents-document")

urlpatterns = [path("", include(router.urls))]

