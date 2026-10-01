from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.ledger.models import Transaction

from . import services
from .forms import RuleForm
from .models import CategorizationRule, UserModel


class SmartCategorizationView(LoginRequiredMixin, View):
    template_name = "categorization/overview.html"

    def context(self, request, form=None):
        user = request.user
        transactions = Transaction.objects.filter(user=user)
        return {
            "model": UserModel.objects.filter(user=user).first(),
            "rules": CategorizationRule.objects.filter(user=user).select_related("category"),
            "form": form or RuleForm(user=user),
            "labelled": services.labelled_transactions(user).count(),
            "min_samples": settings.FINSIGHT_ML_MIN_SAMPLES,
            "threshold": settings.FINSIGHT_ML_CONFIDENCE,
            "uncategorized": transactions.filter(category__isnull=True).count(),
            "auto": transactions.filter(categorized_by=Transaction.Source.ML).count(),
        }

    def get(self, request):
        return render(request, self.template_name, self.context(request))

    def post(self, request):
        """Create a rule and apply it to existing uncategorized transactions."""
        form = RuleForm(request.POST, user=request.user)
        if not form.is_valid():
            return render(request, self.template_name, self.context(request, form))
        form.save()
        applied = services.categorize_uncategorized(request.user)
        messages.success(request, f"Rule saved. {applied} transaction(s) categorized.")
        return redirect("categorization:overview")


class DeleteRuleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        get_object_or_404(CategorizationRule, pk=pk, user=request.user).delete()
        messages.info(request, "Rule deleted.")
        return redirect("categorization:overview")


class RetrainView(LoginRequiredMixin, View):
    def post(self, request):
        model = services.train_user_model(request.user)
        if model is None:
            messages.warning(
                request,
                f"Categorize at least {settings.FINSIGHT_ML_MIN_SAMPLES} transactions "
                "(in two or more categories) to train your personal model.",
            )
        else:
            messages.success(request, f"Model retrained on {model.samples} transactions.")
        return redirect("categorization:overview")


class CategorizeNowView(LoginRequiredMixin, View):
    def post(self, request):
        count = services.categorize_uncategorized(request.user)
        messages.success(request, f"Categorized {count} transaction(s).")
        return redirect("categorization:overview")
