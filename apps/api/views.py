from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.categorization import services as categorization
from apps.insights.analytics import dashboard
from apps.ledger.events import category_corrected
from apps.ledger.filters import TransactionFilter
from apps.ledger.models import Account, Category, Transaction

from .serializers import (
    AccountSerializer,
    CategorizeSerializer,
    CategorySerializer,
    SummarySerializer,
    TransactionSerializer,
)


class OwnedViewSet(viewsets.ModelViewSet):
    model = None

    def get_queryset(self):
        return self.model.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AccountViewSet(OwnedViewSet):
    model = Account
    serializer_class = AccountSerializer

    def get_queryset(self):
        zero = Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))
        return (
            super()
            .get_queryset()
            .annotate(
                current_balance=F("opening_balance") + Coalesce(Sum("transactions__amount"), zero)
            )
        )


class CategoryViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TransactionViewSet(OwnedViewSet):
    """Transactions. Supports the same filters as the web UI (``q``, ``account``,
    ``category``, ``uncategorized``, ``start``, ``end``, ``direction``)."""

    model = Transaction
    serializer_class = TransactionSerializer

    def get_queryset(self):
        base = super().get_queryset().select_related("category")
        return TransactionFilter(
            self.request.query_params or None, queryset=base, user=self.request.user
        ).qs

    def perform_create(self, serializer):
        category = serializer.validated_data.get("category")
        txn = serializer.save(
            user=self.request.user, categorized_by=Transaction.Source.USER if category else ""
        )
        if category is None:
            categorization.categorize(self.request.user, [txn])

    @extend_schema(request=CategorizeSerializer, responses=TransactionSerializer)
    @action(detail=True, methods=["post"])
    def categorize(self, request, pk=None):
        """Set (or clear) the category. Counts as a correction for model retraining."""
        txn = self.get_object()
        payload = CategorizeSerializer(data=request.data, context={"request": request})
        payload.is_valid(raise_exception=True)
        txn.category = payload.validated_data["category"]
        txn.categorized_by = Transaction.Source.USER if txn.category else Transaction.Source.NONE
        txn.confidence = None
        txn.save(update_fields=["category", "categorized_by", "confidence", "updated_at"])
        if txn.category:
            category_corrected.send(sender=Transaction, user=request.user, transaction=txn)
        return Response(TransactionSerializer(txn, context={"request": request}).data)


class SummaryView(APIView):
    """This month's totals, 12-month cash flow, category split and recurring payments."""

    @extend_schema(responses=SummarySerializer)
    def get(self, request):
        return Response(SummarySerializer(dashboard(request.user)).data)
