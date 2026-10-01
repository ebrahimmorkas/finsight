from django import forms

from apps.ledger.models import Category

from .models import CategorizationRule


class RuleForm(forms.ModelForm):
    class Meta:
        model = CategorizationRule
        fields = ["field", "pattern", "category", "priority"]

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["category"].queryset = Category.objects.filter(user=user)

    def clean_pattern(self):
        pattern = self.cleaned_data["pattern"].strip()
        if len(pattern) < 2:
            raise forms.ValidationError("Use at least 2 characters.")
        return pattern

    def save(self, commit=True):
        self.instance.user = self.user
        return super().save(commit)
