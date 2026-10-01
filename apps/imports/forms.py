from django import forms

from apps.ledger.models import Account

from .parser import DAY_FIRST, MONTH_FIRST

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class ImportForm(forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.none())
    file = forms.FileField(
        help_text="CSV export from your bank (max 5 MB).",
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}),
    )
    date_order = forms.ChoiceField(
        label="Dates like 03/04/2026 mean",
        choices=[(DAY_FIRST, "3 April (day first)"), (MONTH_FIRST, "March 4 (month first)")],
        initial=DAY_FIRST,
        help_text="Only used when the file itself is ambiguous.",
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = Account.objects.filter(user=user)

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if upload.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("Files must be 5 MB or smaller.")
        if not upload.name.lower().endswith((".csv", ".txt")):
            raise forms.ValidationError("Please upload a .csv file.")
        return upload
