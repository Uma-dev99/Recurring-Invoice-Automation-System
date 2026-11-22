"""Outbox handlers owned by the invoicing app (registered in InvoicingConfig.ready())."""

from apps.operations.outbox import register_handler


def handle_submit(payload: dict) -> None:
    # Imported inside the function: this module is imported while apps are still
    # loading, when importing models/services at module level isn't allowed yet.
    from apps.invoicing.services import submit

    submit(submission_id=payload["submission_id"])


register_handler("invoice.submit", handle_submit)
