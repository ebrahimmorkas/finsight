from django.urls import path

from . import views

app_name = "budgets"

urlpatterns = [
    path("", views.BudgetOverviewView.as_view(), name="overview"),
    path("new/", views.BudgetCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", views.BudgetUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.BudgetDeleteView.as_view(), name="delete"),
]
