from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView

from .forms import BudgetForm
from .models import Budget
from .services import statuses


class BudgetOverviewView(LoginRequiredMixin, TemplateView):
    template_name = "budgets/overview.html"

    def get_context_data(self, **kwargs):
        items = statuses(self.request.user)
        return super().get_context_data(
            statuses=items,
            total_budget=sum(s.budget.amount for s in items),
            total_spent=sum(s.spent for s in items),
            **kwargs,
        )


class OwnedBudgetMixin(LoginRequiredMixin):
    model = Budget
    form_class = BudgetForm
    template_name = "ledger/form.html"
    success_url = reverse_lazy("budgets:overview")

    def get_queryset(self):
        return Budget.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}


class BudgetCreateView(OwnedBudgetMixin, CreateView):
    extra_context = {"title": "New budget"}


class BudgetUpdateView(OwnedBudgetMixin, UpdateView):
    extra_context = {"title": "Edit budget"}


class BudgetDeleteView(LoginRequiredMixin, DeleteView):
    success_url = reverse_lazy("budgets:overview")
    template_name = "budgets/confirm_delete.html"

    def get_queryset(self):
        return Budget.objects.filter(user=self.request.user)
