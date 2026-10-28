"""
people.py
=========
People in the clinic: patients and staff.

Inheritance hierarchy
---------------------
::

    Person (abstract)
     ├── Patient
     └── Staff
          ├── Doctor
          ├── Nurse
          ├── LabTechnician
          └── Pharmacist

* ``Patient`` *composition* ``MedicalRecord``  - the record is created with
  the patient and belongs only to that patient.
* ``Patient`` *composition* ``EmergencyContact``.
* ``Patient`` *association* ``InsurancePolicy`` and ``UserAccount``.
* ``Staff`` *composition* ``WeeklyHours`` (working hours).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from .emr import MedicalRecord, Visit, Vitals
from .enums import StaffRole
from .exceptions import InvalidStateError, ValidationError
from .hours import WeeklyHours
from .lab import LabOrder, LabResult, LabTest
from .prescriptions import Prescription, PrescriptionItem
from .utils import IdGenerator, to_money

if TYPE_CHECKING:
    from .accounts import UserAccount
    from .billing import InsurancePolicy
    from .clinic import Address, Department, Laboratory
    from .scheduling import Appointment, AppointmentScheduler

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ====================================================================== #
# Base class
# ====================================================================== #
class Person(ABC):
    """Abstract base class holding personal details shared by all people."""

    _ID_PREFIX = "PER"

    def __init__(self, first_name: str, last_name: str, date_of_birth: date,
                 phone: str, email: str, address: Optional[Address] = None) -> None:
        if not first_name.strip() or not last_name.strip():
            raise ValidationError("First and last name are required.")
        if date_of_birth > date.today():
            raise ValidationError("Date of birth cannot be in the future.")
        if not _EMAIL_PATTERN.match(email):
            raise ValidationError(f"Invalid email address: {email!r}")
        self._person_id = IdGenerator.next_id(self._ID_PREFIX)
        self._first_name = first_name.strip()
        self._last_name = last_name.strip()
        self._date_of_birth = date_of_birth
        self.phone = phone
        self._email = email
        self.address = address

    # ---- read-only / validated properties ---- #
    @property
    def person_id(self) -> str:
        return self._person_id

    @property
    def first_name(self) -> str:
        return self._first_name

    @property
    def last_name(self) -> str:
        return self._last_name

    @property
    def full_name(self) -> str:
        return f"{self._first_name} {self._last_name}"

    @property
    def date_of_birth(self) -> date:
        return self._date_of_birth

    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, value: str) -> None:
        if not _EMAIL_PATTERN.match(value):
            raise ValidationError(f"Invalid email address: {value!r}")
        self._email = value

    def age(self, on: Optional[date] = None) -> int:
        """Age in whole years on the given date (default: today)."""
        on = on or date.today()
        had_birthday = (on.month, on.day) >= (self._date_of_birth.month,
                                              self._date_of_birth.day)
        return on.year - self._date_of_birth.year - (0 if had_birthday else 1)

    @abstractmethod
    def role_description(self) -> str:
        """Short description of the person's role (implemented by subclasses)."""

    def __str__(self) -> str:
        return f"{self.full_name} ({self.role_description()}, {self._person_id})"


# ====================================================================== #
# Patient
# ====================================================================== #
class EmergencyContact:
    """Person to contact in an emergency (owned by a Patient)."""

    def __init__(self, name: str, relationship: str, phone: str) -> None:
        self.name = name
        self.relationship = relationship
        self.phone = phone

    def __str__(self) -> str:
        return f"{self.name} ({self.relationship}) - {self.phone}"


class Patient(Person):
    """A patient registered with the clinic."""

    _ID_PREFIX = "PAT"
    _EDITABLE_FIELDS = {"phone", "email", "address", "emergency_contact",
                        "insurance", "medical_history_summary"}

    def __init__(self, first_name: str, last_name: str, date_of_birth: date,
                 phone: str, email: str, address: Optional[Address] = None,
                 emergency_contact: Optional[EmergencyContact] = None,
                 insurance: Optional[InsurancePolicy] = None,
                 allergies: Optional[List[str]] = None,
                 medical_history_summary: str = "") -> None:
        super().__init__(first_name, last_name, date_of_birth, phone, email, address)
        self.emergency_contact = emergency_contact
        self.insurance = insurance
        self._allergies: List[str] = [a.strip() for a in (allergies or [])]
        self.medical_history_summary = medical_history_summary
        self.account: Optional[UserAccount] = None
        # Composition: the medical record is created with (and owned by) the patient
        self._medical_record = MedicalRecord(self)

    def role_description(self) -> str:
        return "Patient"

    @property
    def medical_record(self) -> MedicalRecord:
        return self._medical_record

    @property
    def allergies(self) -> List[str]:
        return list(self._allergies)

    def add_allergy(self, allergy: str) -> None:
        if allergy.strip() and not self.is_allergic_to(allergy):
            self._allergies.append(allergy.strip())

    def is_allergic_to(self, substance: str) -> bool:
        """Case-insensitive check used before prescribing medication."""
        return any(a.lower() == substance.lower() for a in self._allergies)

    def update_profile(self, **changes) -> None:
        """Update editable profile fields (contact details, insurance, etc.)."""
        unknown = set(changes) - self._EDITABLE_FIELDS
        if unknown:
            raise ValidationError(f"Cannot update field(s): {', '.join(sorted(unknown))}")
        for field, value in changes.items():
            setattr(self, field, value)   # email goes through its validating setter

    def upcoming_appointments(self, scheduler: AppointmentScheduler) -> List[Appointment]:
        """Return this patient's future, active appointments in date order."""
        return scheduler.appointments_for_patient(self, upcoming_only=True)

    def download_visit_summary(self, visit_id: str, directory: str = "output") -> Path:
        """Write a visit summary to a text file and return its path.

        Access control is applied by the medical record: a patient can only
        download summaries from their own record.
        """
        visit = self._medical_record.get_visit(visit_id, requester=self)
        folder = Path(directory)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"visit_summary_{visit.visit_id}.txt"
        path.write_text(visit.summary(), encoding="utf-8")
        return path


# ====================================================================== #
# Staff hierarchy
# ====================================================================== #
class Staff(Person):
    """A member of clinic staff."""

    _ID_PREFIX = "STF"

    def __init__(self, first_name: str, last_name: str, date_of_birth: date,
                 phone: str, email: str, role: StaffRole,
                 qualifications: Optional[List[str]] = None,
                 working_hours: Optional[WeeklyHours] = None,
                 address: Optional[Address] = None) -> None:
        super().__init__(first_name, last_name, date_of_birth, phone, email, address)
        self._role = role
        self.qualifications = list(qualifications or [])
        # Composition: each staff member owns their own working-hours object
        self.working_hours = working_hours or WeeklyHours.weekdays("09:00", "17:00")
        self.department: Optional[Department] = None   # set by Department.add_staff

    @property
    def role(self) -> StaffRole:
        return self._role

    def role_description(self) -> str:
        return self._role.value

    def is_working(self, start: datetime, end: datetime) -> bool:
        """True if the period falls inside this person's working hours."""
        return self.working_hours.covers(start, end)


class Doctor(Staff):
    """A doctor who conducts visits, diagnoses, prescribes and orders lab tests."""

    _ID_PREFIX = "DOC"

    def __init__(self, first_name: str, last_name: str, date_of_birth: date,
                 phone: str, email: str, speciality: str, license_number: str,
                 consultation_fee, qualifications: Optional[List[str]] = None,
                 working_hours: Optional[WeeklyHours] = None) -> None:
        super().__init__(first_name, last_name, date_of_birth, phone, email,
                         StaffRole.DOCTOR, qualifications, working_hours)
        self.speciality = speciality
        self._license_number = license_number
        self.consultation_fee = to_money(consultation_fee)

    @property
    def license_number(self) -> str:
        return self._license_number

    @property
    def full_name(self) -> str:
        return f"Dr. {self.first_name} {self.last_name}"

    def role_description(self) -> str:
        return f"Doctor - {self.speciality}"

    # ---------------------- clinical actions ---------------------- #
    def start_visit(self, appointment: Appointment) -> Visit:
        """Open a visit (EMR entry) for one of this doctor's appointments."""
        if appointment.doctor is not self:
            raise InvalidStateError("A doctor can only start visits for their own appointments.")
        if not appointment.is_active:
            raise InvalidStateError(
                f"Cannot start a visit for a {appointment.status.value} appointment.")
        if appointment.visit is not None:
            raise InvalidStateError("A visit has already been recorded for this appointment.")
        visit = Visit(appointment)
        appointment.visit = visit
        appointment.patient.medical_record.add_visit(visit)
        return visit

    def prescribe(self, visit: Visit, items: List[PrescriptionItem]) -> Prescription:
        """Create a prescription for the visit, checking the patient's allergies."""
        self._check_own_visit(visit)
        for item in items:
            if visit.patient.is_allergic_to(item.medication.name):
                raise ValidationError(
                    f"{visit.patient.full_name} is allergic to {item.medication.name}.")
        prescription = Prescription(visit, self, items)
        visit.add_prescription(prescription)
        return prescription

    def order_lab_test(self, visit: Visit, test: LabTest,
                       laboratory: Laboratory, notes: str = "") -> LabOrder:
        """Order a lab test for the visit and send it to the laboratory."""
        self._check_own_visit(visit)
        order = LabOrder(visit, test, self, notes)
        visit.add_lab_order(order)
        laboratory.receive_order(order)
        return order

    def _check_own_visit(self, visit: Visit) -> None:
        if visit.doctor is not self:
            raise InvalidStateError("Doctors can only act on their own visits.")
        if visit.is_closed:
            raise InvalidStateError("The visit is closed and can no longer be changed.")


class Nurse(Staff):
    """A nurse who records patient vitals."""

    _ID_PREFIX = "NUR"

    def __init__(self, first_name: str, last_name: str, date_of_birth: date,
                 phone: str, email: str, **kwargs) -> None:
        super().__init__(first_name, last_name, date_of_birth, phone, email,
                         StaffRole.NURSE, **kwargs)

    def record_vitals(self, visit: Visit, vitals: Vitals) -> None:
        visit.record_vitals(vitals, recorded_by=self)


class LabTechnician(Staff):
    """A laboratory technician who collects samples and uploads results."""

    _ID_PREFIX = "LAB"

    def __init__(self, first_name: str, last_name: str, date_of_birth: date,
                 phone: str, email: str, **kwargs) -> None:
        super().__init__(first_name, last_name, date_of_birth, phone, email,
                         StaffRole.LAB_TECHNICIAN, **kwargs)

    def collect_sample(self, order: LabOrder) -> None:
        order.collect_sample()

    def upload_result(self, order: LabOrder, patient: Patient, visit_id: str,
                      values: Dict[str, str], interpretation: str,
                      is_abnormal: bool = False) -> LabResult:
        """Attach a result to an order after checking patient and visit match."""
        result = LabResult(values, interpretation, is_abnormal, recorded_by=self)
        order.record_result(result, patient=patient, visit_id=visit_id)
        return result


class Pharmacist(Staff):
    """A pharmacist who dispenses prescriptions received by the pharmacy."""

    _ID_PREFIX = "PHA"

    def __init__(self, first_name: str, last_name: str, date_of_birth: date,
                 phone: str, email: str, **kwargs) -> None:
        super().__init__(first_name, last_name, date_of_birth, phone, email,
                         StaffRole.PHARMACIST, **kwargs)

    def dispense(self, prescription: Prescription) -> None:
        prescription.mark_dispensed(self)
