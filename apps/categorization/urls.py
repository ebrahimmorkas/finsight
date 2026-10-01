from django.urls import path

from . import views

app_name = "categorization"

urlpatterns = [
    path("", views.SmartCategorizationView.as_view(), name="overview"),
    path("rules/<int:pk>/delete/", views.DeleteRuleView.as_view(), name="rule-delete"),
    path("retrain/", views.RetrainView.as_view(), name="retrain"),
    path("run/", views.CategorizeNowView.as_view(), name="run"),
]
