from django.apps import AppConfig


class CustomersConfig(AppConfig):
    """The people and companies we bill. Customers are not users: they never log in."""

    name = "apps.customers"
    label = "customers"
