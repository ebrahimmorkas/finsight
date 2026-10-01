from django import forms

from .models import Account, Category, Transaction


class UserScopedForm(forms.ModelForm):
    """Limit foreign-key choices to objects owned by the current user."""

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if "account" in self.fields:
            self.fields["account"].queryset = Account.objects.filter(user=user)
        if "category" in self.fields:
            self.fields["category"].queryset = Category.objects.filter(user=user)
            self.fields["category"].required = False

    def save(self, commit=True):
        self.instance.user = self.user
        return super().save(commit)


class AccountForm(UserScopedForm):
    class Meta:
        model = Account
        fields = ["name", "kind", "currency", "opening_balance"]

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        clash = Account.objects.filter(user=self.user, name__iexact=name).exclude(
            pk=self.instance.pk
        )
        if clash.exists():
            raise forms.ValidationError("You already have an account with this name.")
        return name


class CategoryForm(UserScopedForm):
    class Meta:
        model = Category
        fields = ["name", "kind", "color"]
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        clash = Category.objects.filter(user=self.user, name__iexact=name).exclude(
            pk=self.instance.pk
        )
        if clash.exists():
            raise forms.ValidationError("You already have a category with this name.")
        return name


class TransactionForm(UserScopedForm):
    class Meta:
        model = Transaction
        fields = ["account", "date", "description", "amount", "category", "notes"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}
        help_texts = {"amount": "Use a negative number for spending, e.g. -42.50"}

    def save(self, commit=True):
        if self.cleaned_data.get("category"):
            self.instance.categorized_by = Transaction.Source.USER
            self.instance.confidence = None
        if "description" in self.changed_data:
            self.instance.merchant = ""  # re-normalize
        return super().save(commit)
