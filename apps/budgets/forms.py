from django import forms

from apps.ledger.models import Category

from .models import Budget


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ["category", "amount", "warn_at_percent"]
        labels = {"amount": "Monthly limit", "warn_at_percent": "Warn me at (%)"}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["category"].queryset = Category.objects.filter(
            user=user, kind=Category.Kind.EXPENSE
        )

    def clean_category(self):
        category = self.cleaned_data["category"]
        clash = Budget.objects.filter(user=self.user, category=category).exclude(
            pk=self.instance.pk
        )
        if clash.exists():
            raise forms.ValidationError("This category already has a budget.")
        return category

    def save(self, commit=True):
        self.instance.user = self.user
        return super().save(commit)
