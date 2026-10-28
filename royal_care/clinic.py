"""
clinic.py
=========
Clinic information: the clinic profile, its address and contact details,
and its departments.

Relationships implemented here
------------------------------
* ``Clinic`` *composition* ``Department``  - departments are created for
  and owned by one clinic; they do not exist on their own.
* ``Department`` *aggregation* ``Staff``   - staff are assigned to a
  department but exist independently of it (they can be moved).
* ``Laboratory`` and ``Pharmacy`` *inherit* from ``Department`` and add
  their own catalogues (lab tests / medications).
* ``Clinic`` *composition* ``AppointmentScheduler`` and ``BillingService``.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Dict, List, Optional

from .accounts import UserAccount
from .billing import BillingService
from .exceptions import NotFoundError, ValidationError
from .hours import WeeklyHours
from .people import Doctor, EmergencyContact, Patient, Staff
from .scheduling import AppointmentScheduler

if TYPE_CHECKING:  # imported only for type hints, avoids circular imports
    from .billing import InsurancePolicy
    from .lab import LabOrder, LabTest
    from .prescriptions import Medication, Prescription


# ====================================================================== #
# Value objects
# ====================================================================== #
class Address:
    """Postal address of the clinic or of a person."""

    def __init__(self, street: str, city: str, country: str,
                 postal_code: str = "") -> None:
        self.street = street
        self.city = city
        self.country = country
        self.postal_code = postal_code

    def __str__(self) -> str:
        parts = [self.street, self.city, self.postal_code, self.country]
        return ", ".join(p for p in parts if p)


class ContactInfo:
    """Phone numbers, email and website of the clinic."""

    def __init__(self, phone_numbers: List[str], email: str,
                 website: str = "") -> None:
        if not phone_numbers:
            raise ValidationError("At least one phone number is required.")
        if "@" not in email:
            raise ValidationError(f"Invalid email address: {email!r}")
        self.phone_numbers = list(phone_numbers)
        self.email = email
        self.website = website

    def __str__(self) -> str:
        return (f"Tel: {', '.join(self.phone_numbers)} | Email: {self.email}"
                f" | Web: {self.website or 'n/a'}")


# ====================================================================== #
# Departments
# ====================================================================== #
class Department:
    """A clinical or service department such as Cardiology or Radiology."""

    def __init__(self, name: str, description: str = "",
                 location: str = "", phone: str = "",
                 operating_hours: Optional[WeeklyHours] = None) -> None:
        if not name.strip():
            raise ValidationError("Department name cannot be empty.")
        self._name = name
        self.description = description
        self.location = location
        self.phone = phone
        # Composition: each department owns its own operating hours object
        self.operating_hours = operating_hours or WeeklyHours.weekdays("08:00", "17:00")
        # Aggregation: staff members exist independently of the department
        self._staff: List[Staff] = []

    @property
    def name(self) -> str:
        """Department name (read-only)."""
        return self._name

    @property
    def staff(self) -> List[Staff]:
        """A copy of the staff list so callers cannot modify it directly."""
        return list(self._staff)

    def add_staff(self, member: Staff) -> None:
        """Assign a staff member to this department."""
        if member not in self._staff:
            self._staff.append(member)
            member.department = self

    def remove_staff(self, member: Staff) -> None:
        """Remove a staff member (the staff object itself continues to exist)."""
        if member in self._staff:
            self._staff.remove(member)
            member.department = None

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._name!r}, staff={len(self._staff)})"


class Laboratory(Department):
    """Laboratory department: keeps a test catalogue and receives lab orders."""

    def __init__(self, name: str = "Laboratory", **kwargs) -> None:
        super().__init__(name, **kwargs)
        self._test_catalogue: Dict[str, LabTest] = {}
        self._orders: List[LabOrder] = []

    def add_test(self, test: LabTest) -> None:
        """Add a test (e.g. Full Blood Count) to the catalogue."""
        self._test_catalogue[test.code] = test

    def get_test(self, code: str) -> LabTest:
        """Look up a test by its code."""
        try:
            return self._test_catalogue[code]
        except KeyError:
            raise NotFoundError(f"Lab test {code!r} is not offered.") from None

    @property
    def tests(self) -> List[LabTest]:
        return list(self._test_catalogue.values())

    def receive_order(self, order: LabOrder) -> None:
        """Queue a lab order sent by a doctor."""
        self._orders.append(order)

    def pending_orders(self) -> List[LabOrder]:
        """Orders that do not yet have a result."""
        return [o for o in self._orders if not o.is_complete]


class Pharmacy(Department):
    """Pharmacy department: keeps a formulary and receives prescriptions."""

    def __init__(self, name: str = "Pharmacy", **kwargs) -> None:
        super().__init__(name, **kwargs)
        self._formulary: Dict[str, Medication] = {}
        self._received: List[Prescription] = []

    def add_medication(self, medication: Medication) -> None:
        """Add a medication to the pharmacy formulary."""
        self._formulary[medication.name.lower()] = medication

    def get_medication(self, name: str) -> Medication:
        """Look up a medication by name (case-insensitive)."""
        try:
            return self._formulary[name.lower()]
        except KeyError:
            raise NotFoundError(f"Medication {name!r} is not stocked.") from None

    def receive_prescription(self, prescription: Prescription) -> None:
        """Called by ``Prescription.send_to_pharmacy``."""
        self._received.append(prescription)

    @property
    def received_prescriptions(self) -> List[Prescription]:
        return list(self._received)


# ====================================================================== #
# Clinic (aggregate root / facade)
# ====================================================================== #
class Clinic:
    """The clinic profile and the entry point to all clinic services."""

    _EDITABLE_FIELDS = {"name", "address", "contact"}

    def __init__(self, name: str, address: Address, contact: ContactInfo) -> None:
        self._name = name
        self._address = address
        self._contact = contact
        self._departments: Dict[str, Department] = {}   # composition
        self._staff: Dict[str, Staff] = {}
        self._patients: Dict[str, Patient] = {}
        self._accounts: Dict[str, UserAccount] = {}
        # Composition: services are created with and owned by the clinic
        self.scheduler = AppointmentScheduler(self)
        self.billing = BillingService()

    # ---------------------------- profile ------------------------------ #
    @property
    def name(self) -> str:
        return self._name

    @property
    def address(self) -> Address:
        return self._address

    @property
    def contact(self) -> ContactInfo:
        return self._contact

    def update_info(self, **changes) -> None:
        """Update clinic profile fields: ``name``, ``address`` or ``contact``."""
        unknown = set(changes) - self._EDITABLE_FIELDS
        if unknown:
            raise ValidationError(f"Cannot update field(s): {', '.join(sorted(unknown))}")
        for field, value in changes.items():
            setattr(self, f"_{field}", value)

    def get_info(self) -> Dict[str, object]:
        """Return the clinic profile as a dictionary (easy to display or export)."""
        return {
            "name": self._name,
            "address": str(self._address),
            "phone_numbers": self._contact.phone_numbers,
            "email": self._contact.email,
            "website": self._contact.website,
            "departments": {
                d.name: d.operating_hours.describe() for d in self._departments.values()
            },
        }

    # -------------------------- departments ---------------------------- #
    def add_department(self, department: Department) -> Department:
        """Add a department; names must be unique within the clinic."""
        key = department.name.lower()
        if key in self._departments:
            raise ValidationError(f"Department {department.name!r} already exists.")
        self._departments[key] = department
        return department

    def get_department(self, name: str) -> Department:
        try:
            return self._departments[name.lower()]
        except KeyError:
            raise NotFoundError(f"Department {name!r} not found.") from None

    def update_department(self, name: str, **changes) -> Department:
        """Update description, location, phone or operating_hours of a department."""
        department = self.get_department(name)
        allowed = {"description", "location", "phone", "operating_hours"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValidationError(f"Cannot update field(s): {', '.join(sorted(unknown))}")
        for field, value in changes.items():
            setattr(department, field, value)
        return department

    @property
    def departments(self) -> List[Department]:
        return list(self._departments.values())

    def laboratory(self) -> Laboratory:
        """Return the clinic's laboratory department."""
        return self._first_of_type(Laboratory)

    def pharmacy(self) -> Pharmacy:
        """Return the clinic's pharmacy department."""
        return self._first_of_type(Pharmacy)

    def _first_of_type(self, kind: type) -> Department:
        for dept in self._departments.values():
            if isinstance(dept, kind):
                return dept
        raise NotFoundError(f"The clinic has no {kind.__name__} department.")

    # ----------------------------- staff ------------------------------- #
    def add_staff(self, member: Staff, department_name: str) -> Staff:
        """Register a staff member and assign them to a department."""
        self.get_department(department_name).add_staff(member)
        self._staff[member.person_id] = member
        return member

    def get_staff(self, staff_id: str) -> Staff:
        try:
            return self._staff[staff_id]
        except KeyError:
            raise NotFoundError(f"Staff member {staff_id!r} not found.") from None

    def doctors(self, speciality: Optional[str] = None) -> List[Doctor]:
        """All doctors, optionally filtered by speciality (case-insensitive)."""
        result = [s for s in self._staff.values() if isinstance(s, Doctor)]
        if speciality:
            result = [d for d in result if d.speciality.lower() == speciality.lower()]
        return result

    # ---------------------------- patients ----------------------------- #
    def register_patient(self, first_name: str, last_name: str,
                         date_of_birth: date, phone: str, email: str,
                         address: Address, username: str, password: str,
                         emergency_contact: Optional[EmergencyContact] = None,
                         insurance: Optional[InsurancePolicy] = None,
                         allergies: Optional[List[str]] = None,
                         medical_history_summary: str = "") -> Patient:
        """Create a patient profile together with a login account."""
        if username.lower() in self._accounts:
            raise ValidationError(f"Username {username!r} is already taken.")
        patient = Patient(first_name, last_name, date_of_birth, phone, email,
                          address, emergency_contact, insurance,
                          allergies, medical_history_summary)
        account = UserAccount(username, password, owner=patient)
        patient.account = account
        self._accounts[username.lower()] = account
        self._patients[patient.person_id] = patient
        return patient

    def login(self, username: str, password: str) -> Patient:
        """Return the patient if the credentials are valid."""
        account = self._accounts.get(username.lower())
        if account is None or not account.verify_password(password):
            raise ValidationError("Invalid username or password.")
        return account.owner

    def get_patient(self, patient_id: str) -> Patient:
        try:
            return self._patients[patient_id]
        except KeyError:
            raise NotFoundError(f"Patient {patient_id!r} not found.") from None

    @property
    def patients(self) -> List[Patient]:
        return list(self._patients.values())

    def __repr__(self) -> str:
        return (f"Clinic({self._name!r}, departments={len(self._departments)}, "
                f"staff={len(self._staff)}, patients={len(self._patients)})")
