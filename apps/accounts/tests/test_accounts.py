import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


def test_signup_logs_user_in(client):
    response = client.post(
        reverse("signup"),
        {
            "full_name": "Maya Patel",
            "email": "Maya@Example.com",
            "password1": DEFAULT_PASSWORD,
            "password2": DEFAULT_PASSWORD,
        },
        follow=True,
    )

    assert response.context["user"].is_authenticated
    assert User.objects.get().email == "maya@example.com"


def test_signup_rejects_duplicate_email(client):
    UserFactory(email="taken@example.com")

    response = client.post(
        reverse("signup"),
        {
            "full_name": "X",
            "email": "TAKEN@example.com",
            "password1": DEFAULT_PASSWORD,
            "password2": DEFAULT_PASSWORD,
        },
    )

    assert "email" in response.context["form"].errors


def test_login(client):
    user = UserFactory()

    response = client.post(reverse("login"), {"username": user.email, "password": DEFAULT_PASSWORD})

    assert response.status_code == 302


def test_short_name():
    assert User(full_name="Maya Patel").get_short_name() == "Maya"
    assert User(email="a@b.c").get_short_name() == "a@b.c"
