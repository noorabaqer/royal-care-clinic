"""
exceptions.py
=============
Custom exception hierarchy for the clinic system.

All exceptions inherit from :class:`ClinicError`, so a caller can catch
every domain error with a single ``except ClinicError`` clause while
still being able to handle specific cases individually.
"""


class ClinicError(Exception):
    """Base class for every error raised by the clinic system."""


class ValidationError(ClinicError):
    """Raised when input data is missing or invalid."""


class NotFoundError(ClinicError):
    """Raised when a requested record (patient, doctor, ...) does not exist."""


class SlotUnavailableError(ClinicError):
    """Raised when an appointment slot is already taken or outside working hours."""


class InvalidStateError(ClinicError):
    """Raised when an operation is not allowed in an object's current state."""


class AccessDeniedError(ClinicError):
    """Raised when a user tries to view medical data they are not allowed to see."""


class PaymentError(ClinicError):
    """Raised when a payment cannot be processed."""
