"""
scheduling.py
=============
Appointment scheduling: searching for free slots, booking, rescheduling
and cancelling.

* ``TimeSlot``             - a start/end period (value object).
* ``AvailableSlot``        - a free slot offered by a specific doctor.
* ``Appointment``          - associates one Patient with one Doctor at a TimeSlot.
* ``AppointmentScheduler`` - service owned by the Clinic (composition) that
  keeps all appointments and enforces the booking rules.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional

from .enums import AppointmentStatus
from .exceptions import (InvalidStateError, NotFoundError, SlotUnavailableError,
                         ValidationError)
from .utils import IdGenerator

if TYPE_CHECKING:
    from .clinic import Clinic
    from .emr import Visit
    from .people import Doctor, Patient

DEFAULT_SLOT_MINUTES = 30


# ====================================================================== #
# Value objects
# ====================================================================== #
class TimeSlot:
    """An immutable period of time with a start and an end."""

    def __init__(self, start: datetime, end: datetime) -> None:
        if end <= start:
            raise ValidationError("A time slot must end after it starts.")
        self._start = start
        self._end = end

    @classmethod
    def of_minutes(cls, start: datetime, minutes: int = DEFAULT_SLOT_MINUTES) -> "TimeSlot":
        return cls(start, start + timedelta(minutes=minutes))

    @property
    def start(self) -> datetime:
        return self._start

    @property
    def end(self) -> datetime:
        return self._end

    @property
    def duration_minutes(self) -> int:
        return int((self._end - self._start).total_seconds() // 60)

    def overlaps(self, other: "TimeSlot") -> bool:
        """True if the two slots share any time."""
        return self._start < other.end and other.start < self._end

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, TimeSlot)
                and (self._start, self._end) == (other.start, other.end))

    def __hash__(self) -> int:
        return hash((self._start, self._end))

    def __str__(self) -> str:
        return f"{self._start:%a %d %b %Y %H:%M}-{self._end:%H:%M}"


class AvailableSlot:
    """A free time slot offered by a particular doctor (search result)."""

    def __init__(self, doctor: Doctor, slot: TimeSlot) -> None:
        self.doctor = doctor
        self.slot = slot

    def __repr__(self) -> str:
        return f"AvailableSlot({self.doctor.full_name}, {self.slot})"


# ====================================================================== #
# Appointment
# ====================================================================== #
class Appointment:
    """A booking of a patient with a doctor for a time slot."""

    def __init__(self, patient: Patient, doctor: Doctor, slot: TimeSlot,
                 reason: str = "") -> None:
        self._appointment_id = IdGenerator.next_id("APT")
        self._patient = patient
        self._doctor = doctor
        self._slot = slot
        self.reason = reason
        self._status = AppointmentStatus.BOOKED
        self.created_at = datetime.now()
        self.cancellation_reason: Optional[str] = None
        self.visit: Optional[Visit] = None
        # Audit trail of changes, e.g. reschedules and cancellation
        self._history: List[str] = [f"Booked for {slot}"]

    # ---- read-only properties ---- #
    @property
    def appointment_id(self) -> str:
        return self._appointment_id

    @property
    def patient(self) -> Patient:
        return self._patient

    @property
    def doctor(self) -> Doctor:
        return self._doctor

    @property
    def slot(self) -> TimeSlot:
        return self._slot

    @property
    def status(self) -> AppointmentStatus:
        return self._status

    @property
    def history(self) -> List[str]:
        return list(self._history)

    @property
    def is_active(self) -> bool:
        """BOOKED or RESCHEDULED appointments still occupy the doctor's time."""
        return self._status in (AppointmentStatus.BOOKED, AppointmentStatus.RESCHEDULED)

    # ---- state changes (called by the scheduler / visit) ---- #
    def _reschedule(self, new_slot: TimeSlot) -> None:
        if not self.is_active:
            raise InvalidStateError(
                f"Cannot reschedule a {self._status.value} appointment.")
        self._history.append(f"Rescheduled from {self._slot} to {new_slot}")
        self._slot = new_slot
        self._status = AppointmentStatus.RESCHEDULED

    def _cancel(self, reason: str) -> None:
        if not self.is_active:
            raise InvalidStateError(f"Cannot cancel a {self._status.value} appointment.")
        self._status = AppointmentStatus.CANCELLED
        self.cancellation_reason = reason
        self._history.append(f"Cancelled: {reason}")

    def mark_completed(self) -> None:
        """Called when the visit for this appointment is closed."""
        if not self.is_active:
            raise InvalidStateError(
                f"Cannot complete a {self._status.value} appointment.")
        self._status = AppointmentStatus.COMPLETED
        self._history.append("Completed")

    def __str__(self) -> str:
        return (f"{self._appointment_id}: {self._patient.full_name} with "
                f"{self._doctor.full_name} on {self._slot} [{self._status.value}]")


# ====================================================================== #
# Scheduler service
# ====================================================================== #
class AppointmentScheduler:
    """Keeps all appointments for a clinic and enforces booking rules."""

    def __init__(self, clinic: Clinic) -> None:
        self._clinic = clinic
        self._appointments: Dict[str, Appointment] = {}

    # -------------------------- searching ------------------------------ #
    def search_available_slots(self, on_date: date,
                               doctor: Optional[Doctor] = None,
                               speciality: Optional[str] = None,
                               duration_minutes: int = DEFAULT_SLOT_MINUTES,
                               not_before: Optional[datetime] = None
                               ) -> List[AvailableSlot]:
        """List free slots on ``on_date``, filtered by doctor and/or speciality.

        Slots are generated from each doctor's working hours in steps of
        ``duration_minutes``; any slot overlapping an active appointment is
        left out. ``not_before`` hides slots that have already started.
        """
        if duration_minutes <= 0:
            raise ValidationError("Duration must be a positive number of minutes.")
        doctors = [doctor] if doctor else self._clinic.doctors(speciality)
        if doctor and speciality and doctor.speciality.lower() != speciality.lower():
            return []

        results: List[AvailableSlot] = []
        step = timedelta(minutes=duration_minutes)
        for doc in doctors:
            hours = doc.working_hours.hours_for(on_date.weekday())
            if hours is None:
                continue
            cursor = datetime.combine(on_date, hours[0])
            day_end = datetime.combine(on_date, hours[1])
            while cursor + step <= day_end:
                slot = TimeSlot(cursor, cursor + step)
                if (not_before is None or slot.start >= not_before) \
                        and self._doctor_is_free(doc, slot):
                    results.append(AvailableSlot(doc, slot))
                cursor += step
        results.sort(key=lambda s: (s.slot.start, s.doctor.last_name))
        return results

    # --------------------------- booking ------------------------------- #
    def book(self, patient: Patient, doctor: Doctor, start: datetime,
             duration_minutes: int = DEFAULT_SLOT_MINUTES,
             reason: str = "") -> Appointment:
        """Book an appointment after validating availability."""
        slot = TimeSlot.of_minutes(start, duration_minutes)
        self._validate_slot(patient, doctor, slot)
        appointment = Appointment(patient, doctor, slot, reason)
        self._appointments[appointment.appointment_id] = appointment
        return appointment

    def reschedule(self, appointment_id: str, new_start: datetime,
                   duration_minutes: Optional[int] = None) -> Appointment:
        """Move an appointment to a new start time (same doctor)."""
        appointment = self.get(appointment_id)
        minutes = duration_minutes or appointment.slot.duration_minutes
        new_slot = TimeSlot.of_minutes(new_start, minutes)
        self._validate_slot(appointment.patient, appointment.doctor, new_slot,
                            ignore=appointment)
        appointment._reschedule(new_slot)
        return appointment

    def cancel(self, appointment_id: str, reason: str = "Cancelled by patient") -> Appointment:
        """Cancel an appointment; its slot becomes available again."""
        appointment = self.get(appointment_id)
        appointment._cancel(reason)
        return appointment

    # --------------------------- queries ------------------------------- #
    def get(self, appointment_id: str) -> Appointment:
        try:
            return self._appointments[appointment_id]
        except KeyError:
            raise NotFoundError(f"Appointment {appointment_id!r} not found.") from None

    def appointments_for_patient(self, patient: Patient,
                                 upcoming_only: bool = False,
                                 now: Optional[datetime] = None) -> List[Appointment]:
        now = now or datetime.now()
        items = [a for a in self._appointments.values() if a.patient is patient]
        if upcoming_only:
            items = [a for a in items if a.is_active and a.slot.start >= now]
        return sorted(items, key=lambda a: a.slot.start)

    def appointments_for_doctor(self, doctor: Doctor,
                                on_date: Optional[date] = None) -> List[Appointment]:
        items = [a for a in self._appointments.values() if a.doctor is doctor]
        if on_date:
            items = [a for a in items if a.slot.start.date() == on_date]
        return sorted(items, key=lambda a: a.slot.start)

    # --------------------------- helpers ------------------------------- #
    def _doctor_is_free(self, doctor: Doctor, slot: TimeSlot,
                        ignore: Optional[Appointment] = None) -> bool:
        return not any(
            a.is_active and a is not ignore and a.doctor is doctor
            and a.slot.overlaps(slot)
            for a in self._appointments.values())

    def _validate_slot(self, patient: Patient, doctor: Doctor, slot: TimeSlot,
                       ignore: Optional[Appointment] = None) -> None:
        if not doctor.is_working(slot.start, slot.end):
            raise SlotUnavailableError(
                f"{doctor.full_name} is not working during {slot}.")
        if not self._doctor_is_free(doctor, slot, ignore):
            raise SlotUnavailableError(f"{doctor.full_name} is already booked at {slot}.")
        clash = any(a.is_active and a is not ignore and a.patient is patient
                    and a.slot.overlaps(slot) for a in self._appointments.values())
        if clash:
            raise SlotUnavailableError(
                f"{patient.full_name} already has an appointment at {slot}.")
