from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .filters import TransactionFilter
from .forms import AccountForm, CategoryForm, TransactionForm
from .models import Account, Category, Transaction


class OwnedMixin(LoginRequiredMixin):
    """Every query is restricted to the signed-in user's data."""

    model = None

    def get_queryset(self):
        return self.model.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


# --- accounts ------------------------------------------------------------------------------


class AccountListView(OwnedMixin, ListView):
    model = Account
    template_name = "ledger/accounts.html"
    context_object_name = "accounts"

    def get_queryset(self):
        zero = Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))
        return (
            super()
            .get_queryset()
            .annotate(
                current_balance=F("opening_balance") + Coalesce(Sum("transactions__amount"), zero)
            )
        )


class AccountCreateView(OwnedMixin, CreateView):
    model = Account
    form_class = AccountForm
    template_name = "ledger/form.html"
    success_url = reverse_lazy("ledger:accounts")
    extra_context = {"title": "Add account"}


class AccountUpdateView(OwnedMixin, UpdateView):
    model = Account
    form_class = AccountForm
    template_name = "ledger/form.html"
    success_url = reverse_lazy("ledger:accounts")
    extra_context = {"title": "Edit account"}


# --- categories ----------------------------------------------------------------------------


class CategoryListView(OwnedMixin, ListView):
    model = Category
    template_name = "ledger/categories.html"
    context_object_name = "categories"


class CategoryCreateView(OwnedMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "ledger/form.html"
    success_url = reverse_lazy("ledger:categories")
    extra_context = {"title": "Add category"}


# --- transactions --------------------------------------------------------------------------


class TransactionListView(OwnedMixin, ListView):
    model = Transaction
    template_name = "ledger/transactions.html"
    context_object_name = "transactions"
    paginate_by = 50

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["ledger/_transaction_table.html"]
        return [self.template_name]

    def get_queryset(self):
        base = super().get_queryset().select_related("account", "category")
        self.filterset = TransactionFilter(
            self.request.GET or None, queryset=base, user=self.request.user
        )
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.copy()
        query.pop("page", None)
        context.update(
            filter=self.filterset,
            querystring=query.urlencode(),
            categories=Category.objects.filter(user=self.request.user),
        )
        return context


class TransactionCreateView(OwnedMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "ledger/form.html"
    success_url = reverse_lazy("ledger:transactions")
    extra_context = {"title": "Add transaction"}

    def form_valid(self, form):
        messages.success(self.request, "Transaction added.")
        return super().form_valid(form)


class TransactionUpdateView(OwnedMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "ledger/form.html"
    success_url = reverse_lazy("ledger:transactions")
    extra_context = {"title": "Edit transaction"}


class TransactionDeleteView(OwnedMixin, DeleteView):
    model = Transaction
    success_url = reverse_lazy("ledger:transactions")
    template_name = "ledger/confirm_delete.html"


class SetCategoryView(LoginRequiredMixin, View):
    """Inline re-categorization from the transaction table (HTMX)."""

    def post(self, request, pk):
        transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
        category_id = request.POST.get("category") or None
        category = (
            get_object_or_404(Category, pk=category_id, user=request.user) if category_id else None
        )
        transaction.category = category
        transaction.categorized_by = (
            Transaction.Source.USER if category else Transaction.Source.NONE
        )
        transaction.confidence = None
        transaction.save(update_fields=["category", "categorized_by", "confidence", "updated_at"])
        categories = Category.objects.filter(user=request.user)
        return render(
            request,
            "ledger/_transaction_row.html",
            {"t": transaction, "categories": categories},
        )
