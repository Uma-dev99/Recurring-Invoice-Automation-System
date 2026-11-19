from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Internal staff users and authentication (login/logout/current user).

    Customers are NOT users: customers are billed, staff operate the platform.
    """

    name = "apps.accounts"
    label = "accounts"
