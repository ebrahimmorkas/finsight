from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from . import views

app_name = "api"

router = DefaultRouter()
router.register("accounts", views.AccountViewSet, basename="account")
router.register("categories", views.CategoryViewSet, basename="category")
router.register("transactions", views.TransactionViewSet, basename="transaction")

urlpatterns = [
    path("auth/token/", obtain_auth_token, name="token"),
    path("summary/", views.SummaryView.as_view(), name="summary"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
    *router.urls,
]
