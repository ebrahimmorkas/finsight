from rest_framework import serializers

from apps.ledger.models import Account, Category, Transaction


class UserOwnedRelatedField(serializers.PrimaryKeyRelatedField):
    """Only objects that belong to the requesting user are valid choices."""

    def get_queryset(self):
        return super().get_queryset().filter(user=self.context["request"].user)


class AccountSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = ["id", "name", "kind", "currency", "opening_balance", "balance"]

    def get_balance(self, account) -> str:
        # Annotated in list/detail queries; computed on the fly right after create/update.
        balance = getattr(account, "current_balance", None)
        return f"{account.balance if balance is None else balance:.2f}"


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "kind", "color"]


class TransactionSerializer(serializers.ModelSerializer):
    account = UserOwnedRelatedField(queryset=Account.objects.all())
    category = UserOwnedRelatedField(
        queryset=Category.objects.all(), allow_null=True, required=False
    )
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "account",
            "date",
            "description",
            "merchant",
            "amount",
            "category",
            "category_name",
            "categorized_by",
            "confidence",
            "notes",
        ]
        read_only_fields = ["merchant", "categorized_by", "confidence"]


class CategorizeSerializer(serializers.Serializer):
    category = UserOwnedRelatedField(queryset=Category.objects.all(), allow_null=True)


class RecurringSerializer(serializers.Serializer):
    merchant = serializers.CharField()
    cadence = serializers.CharField()
    average_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    monthly_cost = serializers.DecimalField(max_digits=14, decimal_places=2)
    occurrences = serializers.IntegerField()
    last_date = serializers.DateField()
    next_date = serializers.DateField()


class SummarySerializer(serializers.Serializer):
    income = serializers.DecimalField(max_digits=14, decimal_places=2)
    expenses = serializers.DecimalField(max_digits=14, decimal_places=2)
    net = serializers.DecimalField(max_digits=14, decimal_places=2)
    savings_rate = serializers.FloatField(allow_null=True)
    uncategorized = serializers.IntegerField()
    cashflow = serializers.ListField(child=serializers.DictField())
    categories = serializers.ListField(child=serializers.DictField())
    recurring = RecurringSerializer(many=True)
    recurring_monthly_total = serializers.DecimalField(max_digits=14, decimal_places=2)
