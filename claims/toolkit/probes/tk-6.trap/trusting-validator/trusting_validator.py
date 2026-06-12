"""Counterexample validator: trusts whatever it reads. The tamper probe MUST
go RED against it."""


class RecordError(ValueError):
    pass


def validate_receipt(receipt):
    return None
