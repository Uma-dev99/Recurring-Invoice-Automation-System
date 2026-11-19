from django.contrib.auth.base_user import BaseUserManager


def normalize_email_address(email: str) -> str:
    """Lower-case the whole address.

    Django's built-in normalize_email only lower-cases the domain part. For an internal
    staff tool, treating Alice@Example.com and alice@example.com as different people
    would only cause confusion, so we normalize all of it.
    """
    return email.strip().lower()


class UserManager(BaseUserManager):
    """Manager for a user model that logs in with email instead of username."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        user = self.model(email=normalize_email_address(email), **extra_fields)
        user.set_password(password)  # hashes; set_password(None) => unusable password
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, email: str):
        # Used by authenticate(): makes login case-insensitive as well.
        return self.get(email__iexact=normalize_email_address(email))
