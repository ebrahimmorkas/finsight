from django import forms
from django.contrib.auth.forms import BaseUserCreationForm

from .models import User


class SignUpForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ["full_name", "email"]

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email
