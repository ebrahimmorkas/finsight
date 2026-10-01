from django.urls import path

from . import views

app_name = "imports"

urlpatterns = [
    path("", views.ImportHistoryView.as_view(), name="history"),
    path("new/", views.ImportView.as_view(), name="upload"),
    path("<int:pk>/", views.ImportDetailView.as_view(), name="detail"),
]
