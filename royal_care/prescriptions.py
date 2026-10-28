"""
prescriptions.py
================
Prescriptions and medication management.

* ``Medication``       - an item in the pharmacy formulary with a unit price.
* ``PrescriptionItem`` - drug name, dosage and directions for one medication.
* ``Prescription``     - *composition* of ``PrescriptionItem`` objects; issued
  by a Doctor for a Visit and sent to the Pharmacy.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from .enums import PrescriptionStatus
from .exceptions import InvalidStateError, ValidationError
from .utils import IdGenerator, to_money

if TYPE_CHECKING:
    from .clinic import Pharmacy
    from .emr import Visit
    from .people import Doctor, Patient, Pharmacist


class Medication:
    """A medication available from the pharmacy."""

    def __init__(self, name: str, strength: str, form: str, unit_price) -> None:
        if not name.strip():
            raise ValidationError("Medication name is required.")
        self.name = name.strip()
        self.strength = strength
        self.form = form
        self.unit_price = to_money(unit_price)
        if self.unit_price < 0:
            raise ValidationError("Unit price cannot be negative.")

    def __str__(self) -> str:
        return f"{self.name} {self.strength} {self.form}"


class PrescriptionItem:
    """One line of a prescription: drug, dosage, directions and quantity."""

    def __init__(self, medication: Medication, dosage: str, directions: str,
                 quantity: int, duration_days: int = 0) -> None:
        if quantity <= 0:
            raise ValidationError("Quantity must be at least 1.")
        if not dosage.strip() or not directions.strip():
            raise ValidationError("Dosage and directions are required.")
        self.medication = medication
        self.dosage = dosage
        self.directions = directions
        self.quantity = quantity
        self.duration_days = duration_days

    @property
    def drug_name(self) -> str:
        return self.medication.name

    @property
    def line_total(self) -> Decimal:
        return to_money(self.medication.unit_price * self.quantity)

    def __str__(self) -> str:
        return (f"{self.medication} - {self.dosage}, {self.directions} "
                f"(qty {self.quantity})")


class Prescription:
    """A prescription issued during a visit."""

    def __init__(self, visit: Visit, doctor: Doctor,
                 items: List[PrescriptionItem]) -> None:
        if not items:
            raise ValidationError("A prescription needs at least one item.")
        self._prescription_id = IdGenerator.next_id("RX")
        self._visit = visit
        self._doctor = doctor
        self._items: List[PrescriptionItem] = list(items)   # composition
        self._status = PrescriptionStatus.DRAFT
        self.issued_at = datetime.now()
        self.sent_at: Optional[datetime] = None
        self.pharmacy: Optional[Pharmacy] = None
        self.dispensed_by: Optional[Pharmacist] = None

    @property
    def prescription_id(self) -> str:
        return self._prescription_id

    @property
    def visit(self) -> Visit:
        return self._visit

    @property
    def doctor(self) -> Doctor:
        return self._doctor

    @property
    def patient(self) -> Patient:
        return self._visit.patient

    @property
    def items(self) -> List[PrescriptionItem]:
        return list(self._items)

    @property
    def status(self) -> PrescriptionStatus:
        return self._status

    @property
    def total_cost(self) -> Decimal:
        return to_money(sum((i.line_total for i in self._items), Decimal("0")))

    def add_item(self, item: PrescriptionItem) -> None:
        """Items can only be added while the prescription is still a draft."""
        if self._status is not PrescriptionStatus.DRAFT:
            raise InvalidStateError("Cannot change a prescription after it is sent.")
        self._items.append(item)

    def send_to_pharmacy(self, pharmacy: Pharmacy) -> None:
        """Send the prescription to the pharmacy (DRAFT -> SENT_TO_PHARMACY)."""
        if self._status is not PrescriptionStatus.DRAFT:
            raise InvalidStateError(f"Prescription already {self._status.value}.")
        self._status = PrescriptionStatus.SENT_TO_PHARMACY
        self.sent_at = datetime.now()
        self.pharmacy = pharmacy
        pharmacy.receive_prescription(self)

    def mark_dispensed(self, pharmacist: Pharmacist) -> None:
        """Record that medication was handed to the patient."""
        if self._status is not PrescriptionStatus.SENT_TO_PHARMACY:
            raise InvalidStateError("Only prescriptions sent to the pharmacy can be dispensed.")
        self._status = PrescriptionStatus.DISPENSED
        self.dispensed_by = pharmacist

    def __str__(self) -> str:
        return (f"{self._prescription_id} for {self.patient.full_name} by "
                f"{self._doctor.full_name} [{self._status.value}]")
