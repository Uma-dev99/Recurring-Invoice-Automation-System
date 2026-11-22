from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel

# Letters, digits, ".", "_" and "-"; must start with a letter or digit. Covers typical
# CRM/ERP ids ("C-1042", "ACME_01") and keeps ids safe inside merchant references later.
EXTERNAL_ID_VALIDATOR = RegexValidator(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    "Use letters, digits, '.', '_' or '-', starting with a letter or digit.",
)
COUNTRY_CODE_VALIDATOR = RegexValidator(
    r"^[A-Z]{2}$", "Use a two-letter ISO 3166-1 country code, e.g. NL."
)
# One message for a duplicate, whether Python's check or the database's index catches it.
DUPLICATE_EXTERNAL_ID_MESSAGE = "A customer with this external customer id already exists."


class Customer(TimeStampedModel):
    """Someone we send invoices to.

    This model only declares data and database guarantees. Creating, updating and
    deactivating customers (with audit logging) happens in apps/customers/services.py,
    never by calling .save() from a view.

    Field set (Phase 2 assumption): what an invoice recipient needs, i.e. identity,
    contact email and a postal address. Riverty's exact required fields are verified in
    Phase 6; adding optional fields later is a cheap migration.
    """

    class CustomerType(models.TextChoices):
        PERSON = "PERSON", "Person"
        COMPANY = "COMPANY", "Company"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        # Kept for history; no new agreements can be created for it (enforced in Phase 3).
        INACTIVE = "INACTIVE", "Inactive"

    # The customer's id in the business's existing system (CRM/ERP), entered by staff.
    # Stored exactly as entered: external systems may treat ids case-sensitively.
    external_customer_id = models.CharField(
        max_length=64,
        unique=True,
        validators=[EXTERNAL_ID_VALIDATOR],
        error_messages={"unique": DUPLICATE_EXTERNAL_ID_MESSAGE},
    )
    customer_type = models.CharField(
        max_length=10, choices=CustomerType.choices, default=CustomerType.PERSON
    )
    name = models.CharField(max_length=255)  # person's full name or company legal name
    email = models.EmailField()  # not unique: a company may share one billing mailbox
    phone = models.CharField(max_length=32, blank=True)

    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    postal_code = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
    country_code = models.CharField(max_length=2, validators=[COUNTRY_CODE_VALIDATOR])

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["name"]
        constraints = [
            # `choices=` is only checked by forms/serializers. These CHECKs make the
            # database itself refuse invalid values from bulk_create, raw SQL or bugs.
            models.CheckConstraint(
                condition=Q(status__in=["ACTIVE", "INACTIVE"]),
                name="customers_customer_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(customer_type__in=["PERSON", "COMPANY"]),
                name="customers_customer_type_valid",
            ),
            models.CheckConstraint(
                condition=Q(country_code__regex=r"^[A-Z]{2}$"),
                name="customers_customer_country_code_iso2",
            ),
            # CharField has no NOT-EMPTY rule in SQL: "" satisfies NOT NULL.
            models.CheckConstraint(
                condition=~Q(external_customer_id="") & ~Q(name=""),
                name="customers_customer_required_text_not_empty",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.external_customer_id})"
