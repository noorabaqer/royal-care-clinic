"""
lab.py
======
Laboratory orders and results.

* ``LabTest``   - a test in the laboratory catalogue (code, name, price).
* ``LabOrder``  - a test ordered by a doctor for a specific visit; it moves
  through ORDERED -> SAMPLE_COLLECTED -> COMPLETED.
* ``LabResult`` - *composition*: the result belongs to exactly one order.

A result is only accepted if the patient and visit supplied by the lab
technician match the order, so results cannot be filed against the wrong
patient.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional

from .enums import LabOrderStatus
from .exceptions import InvalidStateError, ValidationError
from .utils import IdGenerator, to_money

if TYPE_CHECKING:
    from .emr import Visit
    from .people import Doctor, Patient, Staff


class LabTest:
    """A laboratory test offered by the clinic."""

    def __init__(self, code: str, name: str, specimen: str, price,
                 turnaround_hours: int = 24) -> None:
        self.code = code.upper()
        self.name = name
        self.specimen = specimen
        self.price = to_money(price)
        self.turnaround_hours = turnaround_hours

    def __str__(self) -> str:
        return f"{self.code} - {self.name} ({self.specimen})"


class LabResult:
    """The outcome of a lab test."""

    def __init__(self, values: Dict[str, str], interpretation: str,
                 is_abnormal: bool = False, recorded_by: Optional[Staff] = None) -> None:
        if not values:
            raise ValidationError("A lab result must contain at least one value.")
        self.values = dict(values)
        self.interpretation = interpretation
        self.is_abnormal = is_abnormal
        self.recorded_by = recorded_by
        self.recorded_at = datetime.now()

    def __str__(self) -> str:
        readings = ", ".join(f"{k}: {v}" for k, v in self.values.items())
        flag = "ABNORMAL" if self.is_abnormal else "normal"
        return f"{readings} -> {self.interpretation} ({flag})"


class LabOrder:
    """A lab test ordered for a visit."""

    def __init__(self, visit: Visit, test: LabTest, ordered_by: Doctor,
                 notes: str = "") -> None:
        self._order_id = IdGenerator.next_id("LBO")
        self._visit = visit
        self._test = test
        self._ordered_by = ordered_by
        self.notes = notes
        self._status = LabOrderStatus.ORDERED
        self.ordered_at = datetime.now()
        self.sample_collected_at: Optional[datetime] = None
        self._result: Optional[LabResult] = None

    # ---- read-only properties ---- #
    @property
    def order_id(self) -> str:
        return self._order_id

    @property
    def visit(self) -> Visit:
        return self._visit

    @property
    def patient(self) -> Patient:
        return self._visit.patient

    @property
    def test(self) -> LabTest:
        return self._test

    @property
    def ordered_by(self) -> Doctor:
        return self._ordered_by

    @property
    def status(self) -> LabOrderStatus:
        return self._status

    @property
    def result(self) -> Optional[LabResult]:
        return self._result

    @property
    def is_complete(self) -> bool:
        return self._status is LabOrderStatus.COMPLETED

    # ---- lifecycle ---- #
    def collect_sample(self) -> None:
        if self._status is not LabOrderStatus.ORDERED:
            raise InvalidStateError(f"Cannot collect sample when order is {self._status.value}.")
        self._status = LabOrderStatus.SAMPLE_COLLECTED
        self.sample_collected_at = datetime.now()

    def record_result(self, result: LabResult, patient: Patient, visit_id: str) -> None:
        """Store the result after confirming it is for the right patient and visit."""
        if patient is not self.patient:
            raise ValidationError(
                f"Result is for {patient.full_name} but order {self._order_id} "
                f"belongs to {self.patient.full_name}.")
        if visit_id != self._visit.visit_id:
            raise ValidationError(
                f"Visit {visit_id} does not match order visit {self._visit.visit_id}.")
        if self._status in (LabOrderStatus.COMPLETED, LabOrderStatus.CANCELLED):
            raise InvalidStateError(f"Order {self._order_id} is already {self._status.value}.")
        if self._status is LabOrderStatus.ORDERED:      # sample taken implicitly
            self.collect_sample()
        self._result = result
        self._status = LabOrderStatus.COMPLETED

    def cancel(self) -> None:
        if self._status is LabOrderStatus.COMPLETED:
            raise InvalidStateError("A completed lab order cannot be cancelled.")
        self._status = LabOrderStatus.CANCELLED

    def __str__(self) -> str:
        return f"{self._order_id}: {self._test.name} for {self.patient.full_name} [{self._status.value}]"
