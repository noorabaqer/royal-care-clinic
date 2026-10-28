"""
emr.py
======
Electronic Medical Records.

* ``MedicalRecord`` - one per patient; *composition* of ``Visit`` objects.
* ``Visit``         - one per completed appointment; *composition* of
  ``Vitals``, ``Diagnosis``, ``Attachment`` and clinical notes, and
  *association* with ``Prescription`` and ``LabOrder``.
* ``AccessPolicy``  - decides who may read a medical record.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

from .exceptions import AccessDeniedError, InvalidStateError, NotFoundError, ValidationError
from .utils import IdGenerator

if TYPE_CHECKING:
    from .lab import LabOrder
    from .people import Doctor, Patient, Person, Staff
    from .prescriptions import Prescription
    from .scheduling import Appointment


# ====================================================================== #
# Small clinical value objects
# ====================================================================== #
class Vitals:
    """Vital signs taken during a visit, with basic range validation."""

    def __init__(self, temperature_c: float, systolic_bp: int, diastolic_bp: int,
                 pulse_bpm: int, respiratory_rate: int, weight_kg: float,
                 height_cm: float, oxygen_saturation: int = 98) -> None:
        self._check(30 <= temperature_c <= 45, "Temperature must be 30-45 °C.")
        self._check(50 <= systolic_bp <= 260 and 30 <= diastolic_bp <= 160,
                    "Blood pressure is outside the plausible range.")
        self._check(20 <= pulse_bpm <= 250, "Pulse must be 20-250 bpm.")
        self._check(0 < weight_kg < 400 and 30 < height_cm < 260,
                    "Weight/height are outside the plausible range.")
        self._check(50 <= oxygen_saturation <= 100, "SpO2 must be 50-100 %.")
        self.temperature_c = temperature_c
        self.systolic_bp = systolic_bp
        self.diastolic_bp = diastolic_bp
        self.pulse_bpm = pulse_bpm
        self.respiratory_rate = respiratory_rate
        self.weight_kg = weight_kg
        self.height_cm = height_cm
        self.oxygen_saturation = oxygen_saturation
        self.recorded_by: Optional[Staff] = None
        self.recorded_at: Optional[datetime] = None

    @staticmethod
    def _check(condition: bool, message: str) -> None:
        if not condition:
            raise ValidationError(message)

    @property
    def blood_pressure(self) -> str:
        return f"{self.systolic_bp}/{self.diastolic_bp} mmHg"

    @property
    def bmi(self) -> float:
        """Body-mass index rounded to one decimal place."""
        metres = self.height_cm / 100
        return round(self.weight_kg / (metres ** 2), 1)

    def __str__(self) -> str:
        return (f"Temp {self.temperature_c} °C | BP {self.blood_pressure} | "
                f"Pulse {self.pulse_bpm} bpm | RR {self.respiratory_rate}/min | "
                f"SpO2 {self.oxygen_saturation}% | BMI {self.bmi}")


class Diagnosis:
    """A diagnosis with an ICD-10 code."""

    def __init__(self, code: str, description: str, is_primary: bool = False) -> None:
        if not code.strip() or not description.strip():
            raise ValidationError("Diagnosis code and description are required.")
        self.code = code.upper().strip()
        self.description = description.strip()
        self.is_primary = is_primary

    def __str__(self) -> str:
        flag = " (primary)" if self.is_primary else ""
        return f"{self.code} - {self.description}{flag}"


class Attachment:
    """A file attached to a visit, e.g. a scanned referral letter."""

    def __init__(self, file_name: str, content: bytes, file_type: str = "application/pdf",
                 description: str = "") -> None:
        if not content:
            raise ValidationError("An attachment cannot be empty.")
        self.attachment_id = IdGenerator.next_id("ATT")
        self.file_name = file_name
        self.file_type = file_type
        self.description = description
        self._content = content
        self.uploaded_at = datetime.now()

    @property
    def size_bytes(self) -> int:
        return len(self._content)

    @property
    def content(self) -> bytes:
        return self._content

    def __str__(self) -> str:
        return f"{self.file_name} ({self.file_type}, {self.size_bytes} bytes)"


class ClinicalNote:
    """A timestamped note written during a visit."""

    def __init__(self, text: str, author: Staff) -> None:
        self.text = text
        self.author = author
        self.written_at = datetime.now()

    def __str__(self) -> str:
        return f"[{self.written_at:%H:%M}] {self.author.full_name}: {self.text}"


# ====================================================================== #
# Visit
# ====================================================================== #
class Visit:
    """Everything recorded during one consultation (one per appointment)."""

    def __init__(self, appointment: Appointment) -> None:
        self._visit_id = IdGenerator.next_id("VIS")
        self._appointment = appointment
        self.started_at = datetime.now()
        self.closed_at: Optional[datetime] = None
        self._notes: List[ClinicalNote] = []
        self._vitals: Optional[Vitals] = None
        self._diagnoses: List[Diagnosis] = []
        self._attachments: List[Attachment] = []
        self._prescriptions: List[Prescription] = []
        self._lab_orders: List[LabOrder] = []

    # ---- links back to the appointment ---- #
    @property
    def visit_id(self) -> str:
        return self._visit_id

    @property
    def appointment(self) -> Appointment:
        return self._appointment

    @property
    def patient(self) -> Patient:
        return self._appointment.patient

    @property
    def doctor(self) -> Doctor:
        return self._appointment.doctor

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None

    # ---- read-only views of the collections ---- #
    @property
    def notes(self) -> List[ClinicalNote]:
        return list(self._notes)

    @property
    def vitals(self) -> Optional[Vitals]:
        return self._vitals

    @property
    def diagnoses(self) -> List[Diagnosis]:
        return list(self._diagnoses)

    @property
    def attachments(self) -> List[Attachment]:
        return list(self._attachments)

    @property
    def prescriptions(self) -> List[Prescription]:
        return list(self._prescriptions)

    @property
    def lab_orders(self) -> List[LabOrder]:
        return list(self._lab_orders)

    # ---- recording clinical data ---- #
    def _ensure_open(self) -> None:
        if self.is_closed:
            raise InvalidStateError(f"Visit {self._visit_id} is closed.")

    def add_note(self, text: str, author: Staff) -> None:
        self._ensure_open()
        self._notes.append(ClinicalNote(text, author))

    def record_vitals(self, vitals: Vitals, recorded_by: Staff) -> None:
        self._ensure_open()
        vitals.recorded_by = recorded_by
        vitals.recorded_at = datetime.now()
        self._vitals = vitals

    def add_diagnosis(self, diagnosis: Diagnosis) -> None:
        self._ensure_open()
        if diagnosis.is_primary and any(d.is_primary for d in self._diagnoses):
            raise ValidationError("A visit can only have one primary diagnosis.")
        self._diagnoses.append(diagnosis)

    def add_attachment(self, attachment: Attachment) -> None:
        self._ensure_open()
        self._attachments.append(attachment)

    def add_prescription(self, prescription: Prescription) -> None:
        self._ensure_open()
        self._prescriptions.append(prescription)

    def add_lab_order(self, order: LabOrder) -> None:
        self._ensure_open()
        self._lab_orders.append(order)

    def close(self) -> None:
        """Finish the visit and mark the appointment as COMPLETED."""
        self._ensure_open()
        self.closed_at = datetime.now()
        self._appointment.mark_completed()

    # ---- reporting ---- #
    def summary(self) -> str:
        """Plain-text visit summary for patients and staff."""
        appt = self._appointment
        lines = [
            "ROYAL CARE CLINIC - VISIT SUMMARY",
            "=" * 48,
            f"Visit ID     : {self._visit_id}",
            f"Appointment  : {appt.appointment_id} ({appt.slot})",
            f"Patient      : {self.patient.full_name} ({self.patient.person_id})",
            f"Doctor       : {self.doctor.full_name} - {self.doctor.speciality}",
            f"Reason       : {appt.reason or 'n/a'}",
            "",
            f"Vitals       : {self._vitals or 'not recorded'}",
            "Diagnoses    :",
        ]
        lines += [f"  - {d}" for d in self._diagnoses] or ["  - none"]
        lines.append("Prescriptions:")
        rx_lines = [f"  - {item}" for rx in self._prescriptions for item in rx.items]
        lines += rx_lines or ["  - none"]
        lines.append("Lab orders   :")
        lines += [f"  - {o.test.name}: {o.status.value}"
                  + (f" -> {o.result.interpretation}" if o.result else "")
                  for o in self._lab_orders] or ["  - none"]
        lines.append("Notes        :")
        lines += [f"  - {n.text}" for n in self._notes] or ["  - none"]
        if self._attachments:
            lines.append("Attachments  :")
            lines += [f"  - {a}" for a in self._attachments]
        return "\n".join(lines) + "\n"


# ====================================================================== #
# Medical record and access control
# ====================================================================== #
class AccessPolicy:
    """Rules for who may read a patient's medical record.

    * any member of clinic staff may view visit summaries;
    * a patient may view only their own record;
    * anyone else is refused.
    """

    @staticmethod
    def can_view(requester: Person, record: MedicalRecord) -> bool:
        from .people import Patient, Staff   # local import avoids a cycle
        if isinstance(requester, Staff):
            return True
        if isinstance(requester, Patient):
            return requester is record.patient
        return False


class MedicalRecord:
    """A patient's medical record: the collection of all their visits."""

    def __init__(self, patient: Patient) -> None:
        self._record_id = IdGenerator.next_id("EMR")
        self._patient = patient
        self._visits: Dict[str, Visit] = {}

    @property
    def record_id(self) -> str:
        return self._record_id

    @property
    def patient(self) -> Patient:
        return self._patient

    def add_visit(self, visit: Visit) -> None:
        if visit.patient is not self._patient:
            raise ValidationError("Visit belongs to a different patient.")
        self._visits[visit.visit_id] = visit

    def _authorise(self, requester: Person) -> None:
        if not AccessPolicy.can_view(requester, self):
            raise AccessDeniedError(
                f"{requester.full_name} is not allowed to view this medical record.")

    def get_visit(self, visit_id: str, requester: Person) -> Visit:
        """Return a visit after checking the requester's access rights."""
        self._authorise(requester)
        try:
            return self._visits[visit_id]
        except KeyError:
            raise NotFoundError(f"Visit {visit_id!r} not found in this record.") from None

    def visits(self, requester: Person) -> List[Visit]:
        """All visits in date order, after an access check."""
        self._authorise(requester)
        return sorted(self._visits.values(), key=lambda v: v.appointment.slot.start)

    def __len__(self) -> int:
        return len(self._visits)
