from django.urls import path

from . import views

app_name = "ledger"

urlpatterns = [
    path("transactions/", views.TransactionListView.as_view(), name="transactions"),
    path("transactions/new/", views.TransactionCreateView.as_view(), name="transaction-create"),
    path(
        "transactions/<int:pk>/edit/",
        views.TransactionUpdateView.as_view(),
        name="transaction-edit",
    ),
    path(
        "transactions/<int:pk>/delete/",
        views.TransactionDeleteView.as_view(),
        name="transaction-delete",
    ),
    path("transactions/<int:pk>/category/", views.SetCategoryView.as_view(), name="set-category"),
    path("accounts/", views.AccountListView.as_view(), name="accounts"),
    path("accounts/new/", views.AccountCreateView.as_view(), name="account-create"),
    path("accounts/<int:pk>/edit/", views.AccountUpdateView.as_view(), name="account-edit"),
    path("categories/", views.CategoryListView.as_view(), name="categories"),
    path("categories/new/", views.CategoryCreateView.as_view(), name="category-create"),
]
