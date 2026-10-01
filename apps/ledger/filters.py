import django_filters
from django import forms
from django.db.models import Q

from .models import Account, Category, Transaction


class TransactionFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="search", label="Search")
    account = django_filters.ModelChoiceFilter(queryset=Account.objects.none())
    category = django_filters.ModelChoiceFilter(queryset=Category.objects.none())
    uncategorized = django_filters.BooleanFilter(
        field_name="category",
        lookup_expr="isnull",
        label="Only uncategorized",
        widget=forms.CheckboxInput,
    )
    start = django_filters.DateFilter(
        field_name="date", lookup_expr="gte", widget=forms.DateInput(attrs={"type": "date"})
    )
    end = django_filters.DateFilter(
        field_name="date", lookup_expr="lte", widget=forms.DateInput(attrs={"type": "date"})
    )
    direction = django_filters.ChoiceFilter(
        choices=[("out", "Money out"), ("in", "Money in")], method="filter_direction"
    )

    class Meta:
        model = Transaction
        fields = []

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["account"].queryset = Account.objects.filter(user=user)
        self.filters["category"].queryset = Category.objects.filter(user=user)

    def search(self, queryset, name, value):
        return queryset.filter(
            Q(description__icontains=value)
            | Q(merchant__icontains=value)
            | Q(notes__icontains=value)
        )

    def filter_direction(self, queryset, name, value):
        return queryset.filter(amount__lt=0) if value == "out" else queryset.filter(amount__gt=0)
