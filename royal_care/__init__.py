"""
Royal Care Clinic Management System
===================================
Object-oriented model of an outpatient clinic: clinic information,
patients, staff, appointments, electronic medical records, prescriptions,
laboratory orders and billing.

The most commonly used classes are re-exported here so that callers can
simply write ``from royal_care import Clinic, Patient, Doctor``.
"""

from .accounts import UserAccount
from .billing import (BillingService, CardPayment, InsuranceClaimPayment,
                      InsurancePolicy, Invoice, InvoiceLineItem,
                      MobileWalletPayment, Payment)
from .clinic import Address, Clinic, ContactInfo, Department, Laboratory, Pharmacy
from .emr import AccessPolicy, Attachment, Diagnosis, MedicalRecord, Visit, Vitals
from .enums import (AppointmentStatus, ChargeCategory, InvoiceStatus, LabOrderStatus,
                    PaymentStatus, PrescriptionStatus, StaffRole)
from .exceptions import (AccessDeniedError, ClinicError, InvalidStateError,
                         NotFoundError, PaymentError, SlotUnavailableError,
                         ValidationError)
from .hours import WeeklyHours
from .lab import LabOrder, LabResult, LabTest
from .people import (Doctor, EmergencyContact, LabTechnician, Nurse, Patient,
                     Person, Pharmacist, Staff)
from .prescriptions import Medication, Prescription, PrescriptionItem
from .scheduling import Appointment, AppointmentScheduler, AvailableSlot, TimeSlot

__all__ = [name for name in dir() if not name.startswith("_")]
__version__ = "1.0.0"
