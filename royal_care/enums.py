"""
enums.py
========
Enumerations shared across the Royal Care Clinic Management System.

Using ``Enum`` instead of raw strings means a typo such as ``"COMPLETD"``
is caught straight away, and every legal state of an object is listed
in one place.
"""

from enum import Enum


class StaffRole(Enum):
    """Roles a member of staff can hold in the clinic."""

    DOCTOR = "Doctor"
    NURSE = "Nurse"
    LAB_TECHNICIAN = "Lab Technician"
    PHARMACIST = "Pharmacist"
    RECEPTIONIST = "Receptionist"


class AppointmentStatus(Enum):
    """Lifecycle of an appointment."""

    BOOKED = "BOOKED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class PrescriptionStatus(Enum):
    """Lifecycle of a prescription."""

    DRAFT = "DRAFT"
    SENT_TO_PHARMACY = "SENT_TO_PHARMACY"
    DISPENSED = "DISPENSED"


class LabOrderStatus(Enum):
    """Lifecycle of a laboratory order."""

    ORDERED = "ORDERED"
    SAMPLE_COLLECTED = "SAMPLE_COLLECTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class InvoiceStatus(Enum):
    """Payment state of an invoice."""

    UNPAID = "UNPAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"


class PaymentStatus(Enum):
    """Outcome of a single payment attempt."""

    PENDING = "PENDING"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"


class ChargeCategory(Enum):
    """Category of a line on an invoice."""

    CONSULTATION = "Consultation"
    LAB = "Laboratory"
    MEDICATION = "Medication"
    OTHER = "Other Service"
