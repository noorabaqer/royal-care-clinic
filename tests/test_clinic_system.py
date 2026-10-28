"""
test_clinic_system.py
=====================
Test cases for the Royal Care Clinic Management System.

Each ``TestCase`` class covers one feature from the assignment brief:

    TestClinicInformation          - clinic profile and departments
    TestPatientAccountCreation     - (a) patient account creation
    TestSearchAvailableAppointments- (b) searching for free slots
    TestMakeAppointment            - (c) booking / rescheduling
    TestVisitRecordingAndEMR       - (d) visit, diagnosis, vitals, access control
    TestPrescriptionGeneration     - (e) prescriptions sent to the pharmacy
    TestLabOrderLifecycle          - (f) lab order ORDERED -> COMPLETED
    TestInvoiceAndPayment          - (g) invoice, insurance, payments
    TestAppointmentCancellation    - (h) cancelling appointments
    TestExampleScenarios           - two complete end-to-end examples

Run from the project root with:
    python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from decimal import Decimal

# Make the project root importable when the file is run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from royal_care import (AccessDeniedError, AppointmentStatus, CardPayment,  # noqa: E402
                        ChargeCategory, Diagnosis, EmergencyContact,
                        InsuranceClaimPayment, InsurancePolicy, InvalidStateError,
                        InvoiceStatus, LabOrderStatus, LabTechnician, MobileWalletPayment,
                        Nurse, PaymentError, PaymentStatus, Pharmacist,
                        PrescriptionItem, PrescriptionStatus, SlotUnavailableError,
                        ValidationError, Vitals)
from royal_care.clinic import Address, Department  # noqa: E402
from royal_care.sample_data import build_royal_care_clinic  # noqa: E402
from royal_care.utils import IdGenerator, next_weekday  # noqa: E402


class ClinicTestBase(unittest.TestCase):
    """Shared fixture: a fresh clinic, one insured patient and helper methods."""

    def setUp(self) -> None:
        IdGenerator.reset()                         # independent IDs per test
        self.clinic = build_royal_care_clinic()
        self.monday = next_weekday(date.today(), 0)
        self.dr_brown = self.clinic.doctors("General Practice")[0]
        self.dr_okafor = self.clinic.doctors("Cardiology")[0]
        self.lab = self.clinic.laboratory()
        self.pharmacy = self.clinic.pharmacy()
        self.nurse = next(s for s in self.clinic.get_department("General Practice").staff
                          if isinstance(s, Nurse))
        self.technician = next(s for s in self.lab.staff if isinstance(s, LabTechnician))
        self.pharmacist = next(s for s in self.pharmacy.staff if isinstance(s, Pharmacist))
        self.policy = InsurancePolicy("Sagicor Health", "SH-1001", 80, 20, 5000,
                                      date.today() + timedelta(days=365))
        self.aliyah = self.clinic.register_patient(
            "Aliyah", "Johnson", date(1996, 7, 19), "+1 876 555 0199",
            "aliyah@example.com", Address("27 Palm Ave", "Kingston", "Jamaica"),
            "aliyahj", "Secure#2026",
            EmergencyContact("Marcus Johnson", "Brother", "+1 876 555 0177"),
            self.policy, ["Penicillin V"], "Mild asthma")

    # ---- helpers ---- #
    def at(self, hour: int, minute: int = 0, day: date = None) -> datetime:
        return datetime.combine(day or self.monday, time(hour, minute))

    def book_and_start_visit(self):
        appt = self.clinic.scheduler.book(self.aliyah, self.dr_brown, self.at(10), 30,
                                          "Sore throat")
        return appt, self.dr_brown.start_visit(appt)


# ====================================================================== #
class TestClinicInformation(ClinicTestBase):
    """Clinic profile: add, update and retrieve information."""

    def test_profile_is_retrievable(self):
        info = self.clinic.get_info()
        self.assertEqual(info["name"], "Royal Care Clinic")
        self.assertIn("+1 876 555 0100", info["phone_numbers"])
        for name in ("General Practice", "Cardiology", "Paediatrics",
                     "Laboratory", "Radiology", "Pharmacy"):
            self.assertIn(name, info["departments"])

    def test_update_clinic_info(self):
        self.clinic.update_info(name="Royal Care Clinic - Kingston")
        self.assertEqual(self.clinic.name, "Royal Care Clinic - Kingston")
        with self.assertRaises(ValidationError):
            self.clinic.update_info(owner="Someone")

    def test_department_add_update_and_duplicates(self):
        self.clinic.add_department(Department("Dermatology", location="Wing D"))
        self.clinic.update_department("Dermatology", phone="ext. 400")
        self.assertEqual(self.clinic.get_department("dermatology").phone, "ext. 400")
        with self.assertRaises(ValidationError):
            self.clinic.add_department(Department("Cardiology"))

    def test_department_operating_hours(self):
        gp = self.clinic.get_department("General Practice")
        self.assertEqual(gp.operating_hours.describe()[5], "Saturday: 09:00-13:00")
        self.assertIsNone(gp.operating_hours.hours_for(6))     # closed Sunday


# ====================================================================== #
class TestPatientAccountCreation(ClinicTestBase):
    """(a) Create a patient and confirm the data is stored correctly."""

    def test_patient_details_are_stored(self):
        stored = self.clinic.get_patient(self.aliyah.person_id)
        self.assertIs(stored, self.aliyah)
        self.assertEqual(stored.full_name, "Aliyah Johnson")
        self.assertEqual(stored.date_of_birth, date(1996, 7, 19))
        self.assertEqual(stored.emergency_contact.relationship, "Brother")
        self.assertEqual(stored.insurance.policy_number, "SH-1001")
        self.assertTrue(stored.is_allergic_to("penicillin v"))
        self.assertEqual(stored.account.username, "aliyahj")
        self.assertTrue(stored.person_id.startswith("PAT-"))

    def test_login_and_password_hashing(self):
        self.assertIs(self.clinic.login("aliyahj", "Secure#2026"), self.aliyah)
        with self.assertRaises(ValidationError):
            self.clinic.login("aliyahj", "wrong-password")

    def test_duplicate_username_and_invalid_data_rejected(self):
        with self.assertRaises(ValidationError):
            self.clinic.register_patient("A", "B", date(2000, 1, 1), "1", "a@b.com",
                                         None, "AliyahJ", "Password#1")
        with self.assertRaises(ValidationError):
            self.clinic.register_patient("A", "B", date(2000, 1, 1), "1", "not-an-email",
                                         None, "newuser", "Password#1")
        with self.assertRaises(ValidationError):
            self.clinic.register_patient("A", "B", date(2000, 1, 1), "1", "a@b.com",
                                         None, "newuser", "short")

    def test_update_profile(self):
        self.aliyah.update_profile(phone="+1 876 000 0000", email="new@example.com")
        self.assertEqual(self.aliyah.phone, "+1 876 000 0000")
        self.assertEqual(self.aliyah.email, "new@example.com")
        with self.assertRaises(ValidationError):
            self.aliyah.update_profile(date_of_birth=date(2000, 1, 1))


# ====================================================================== #
class TestSearchAvailableAppointments(ClinicTestBase):
    """(b) Doctor schedules produce the correct list of free slots."""

    def test_lists_all_slots_from_working_hours(self):
        slots = self.clinic.scheduler.search_available_slots(self.monday, doctor=self.dr_brown)
        # Dr Brown works 09:00-12:00 -> six 30-minute slots
        self.assertEqual(len(slots), 6)
        self.assertEqual(slots[0].slot.start, self.at(9))
        self.assertEqual(slots[-1].slot.end, self.at(12))

    def test_booked_slot_is_excluded(self):
        self.clinic.scheduler.book(self.aliyah, self.dr_brown, self.at(10))
        starts = [s.slot.start for s in
                  self.clinic.scheduler.search_available_slots(self.monday, doctor=self.dr_brown)]
        self.assertNotIn(self.at(10), starts)
        self.assertEqual(len(starts), 5)

    def test_search_by_speciality_and_date(self):
        cardio = self.clinic.scheduler.search_available_slots(self.monday, speciality="cardiology")
        self.assertTrue(cardio)
        self.assertTrue(all(s.doctor is self.dr_okafor for s in cardio))
        all_slots = self.clinic.scheduler.search_available_slots(self.monday)
        self.assertEqual(len(all_slots), 6 + 6 + 12)        # Brown + Okafor + Patel
        saturday = self.monday + timedelta(days=5)
        self.assertEqual(self.clinic.scheduler.search_available_slots(saturday), [])

    def test_custom_duration(self):
        slots = self.clinic.scheduler.search_available_slots(
            self.monday, doctor=self.dr_brown, duration_minutes=60)
        self.assertEqual(len(slots), 3)


# ====================================================================== #
class TestMakeAppointment(ClinicTestBase):
    """(c) Book an appointment with a doctor and confirm its status."""

    def test_booking_confirms_status(self):
        appt = self.clinic.scheduler.book(self.aliyah, self.dr_brown, self.at(9, 30),
                                          30, "Check-up")
        self.assertEqual(appt.status, AppointmentStatus.BOOKED)
        self.assertIs(appt.doctor, self.dr_brown)
        self.assertEqual(appt.slot.duration_minutes, 30)
        self.assertEqual(self.aliyah.upcoming_appointments(self.clinic.scheduler), [appt])

    def test_double_booking_and_out_of_hours_rejected(self):
        self.clinic.scheduler.book(self.aliyah, self.dr_brown, self.at(10))
        other = self.clinic.register_patient("Jo", "Doe", date(1980, 1, 1), "1",
                                             "jo@example.com", None, "jodoe", "Password#1")
        with self.assertRaises(SlotUnavailableError):
            self.clinic.scheduler.book(other, self.dr_brown, self.at(10, 15))
        with self.assertRaises(SlotUnavailableError):
            self.clinic.scheduler.book(other, self.dr_brown, self.at(15))
        with self.assertRaises(SlotUnavailableError):       # patient already busy
            self.clinic.scheduler.book(self.aliyah, self.clinic.doctors("Paediatrics")[0],
                                       self.at(10))

    def test_reschedule(self):
        appt = self.clinic.scheduler.book(self.aliyah, self.dr_brown, self.at(9))
        self.clinic.scheduler.reschedule(appt.appointment_id, self.at(11))
        self.assertEqual(appt.status, AppointmentStatus.RESCHEDULED)
        self.assertEqual(appt.slot.start, self.at(11))
        self.assertEqual(len(appt.history), 2)
        # the old slot is free again
        starts = [s.slot.start for s in
                  self.clinic.scheduler.search_available_slots(self.monday, doctor=self.dr_brown)]
        self.assertIn(self.at(9), starts)


# ====================================================================== #
class TestVisitRecordingAndEMR(ClinicTestBase):
    """(d) Record a visit with diagnosis and vitals linked to the appointment."""

    def test_visit_links_to_appointment_and_record(self):
        appt, visit = self.book_and_start_visit()
        self.nurse.record_vitals(visit, Vitals(38.1, 120, 80, 92, 18, 64, 167))
        visit.add_diagnosis(Diagnosis("J02.9", "Acute pharyngitis", is_primary=True))
        self.assertIs(visit.appointment, appt)
        self.assertIs(appt.visit, visit)
        self.assertIs(visit.patient, self.aliyah)
        self.assertEqual(visit.vitals.temperature_c, 38.1)
        self.assertEqual(visit.vitals.bmi, 22.9)
        self.assertEqual(visit.diagnoses[0].code, "J02.9")
        self.assertIs(self.aliyah.medical_record.get_visit(visit.visit_id, self.dr_brown), visit)

    def test_closing_visit_completes_appointment_and_locks_it(self):
        appt, visit = self.book_and_start_visit()
        visit.close()
        self.assertEqual(appt.status, AppointmentStatus.COMPLETED)
        with self.assertRaises(InvalidStateError):
            visit.add_note("late note", self.dr_brown)

    def test_validation_rules(self):
        _, visit = self.book_and_start_visit()
        visit.add_diagnosis(Diagnosis("J02.9", "Pharyngitis", is_primary=True))
        with self.assertRaises(ValidationError):
            visit.add_diagnosis(Diagnosis("R50.9", "Fever", is_primary=True))
        with self.assertRaises(ValidationError):
            Vitals(55, 120, 80, 80, 16, 70, 170)           # impossible temperature
        with self.assertRaises(InvalidStateError):
            self.dr_okafor.start_visit(visit.appointment)   # not his appointment

    def test_access_control_and_summary_download(self):
        _, visit = self.book_and_start_visit()
        visit.add_diagnosis(Diagnosis("J02.9", "Acute pharyngitis"))
        stranger = self.clinic.register_patient("Sam", "Lee", date(1985, 5, 5), "1",
                                                "sam@example.com", None, "samlee", "Password#1")
        with self.assertRaises(AccessDeniedError):
            self.aliyah.medical_record.get_visit(visit.visit_id, requester=stranger)
        self.assertEqual(len(self.aliyah.medical_record.visits(self.nurse)), 1)
        with tempfile.TemporaryDirectory() as folder:
            path = self.aliyah.download_visit_summary(visit.visit_id, folder)
            text = path.read_text(encoding="utf-8")
        self.assertIn("Acute pharyngitis", text)
        self.assertIn(visit.visit_id, text)


# ====================================================================== #
class TestPrescriptionGeneration(ClinicTestBase):
    """(e) Doctor creates a prescription; it is marked as sent to the pharmacy."""

    def test_prescription_sent_to_pharmacy(self):
        _, visit = self.book_and_start_visit()
        rx = self.dr_brown.prescribe(visit, [PrescriptionItem(
            self.pharmacy.get_medication("Amoxicillin"), "500 mg",
            "1 capsule three times daily", 21, 7)])
        self.assertEqual(rx.status, PrescriptionStatus.DRAFT)
        rx.send_to_pharmacy(self.pharmacy)
        self.assertEqual(rx.status, PrescriptionStatus.SENT_TO_PHARMACY)
        self.assertIn(rx, self.pharmacy.received_prescriptions)
        self.assertEqual(rx.items[0].drug_name, "Amoxicillin")
        self.assertEqual(rx.total_cost, Decimal("16.80"))
        self.pharmacist.dispense(rx)
        self.assertEqual(rx.status, PrescriptionStatus.DISPENSED)

    def test_allergy_and_state_rules(self):
        _, visit = self.book_and_start_visit()
        with self.assertRaises(ValidationError):
            self.dr_brown.prescribe(visit, [PrescriptionItem(
                self.pharmacy.get_medication("Penicillin V"), "250 mg", "four times daily", 28)])
        rx = self.dr_brown.prescribe(visit, [PrescriptionItem(
            self.pharmacy.get_medication("Paracetamol"), "1 g", "every 6 hours", 20)])
        rx.send_to_pharmacy(self.pharmacy)
        with self.assertRaises(InvalidStateError):
            rx.add_item(PrescriptionItem(self.pharmacy.get_medication("Ibuprofen"),
                                         "400 mg", "twice daily", 10))
        with self.assertRaises(InvalidStateError):
            rx.send_to_pharmacy(self.pharmacy)


# ====================================================================== #
class TestLabOrderLifecycle(ClinicTestBase):
    """(f) Doctor orders a lab test, result received, status COMPLETED."""

    def test_full_lifecycle(self):
        _, visit = self.book_and_start_visit()
        order = self.dr_brown.order_lab_test(visit, self.lab.get_test("FBC"), self.lab)
        self.assertEqual(order.status, LabOrderStatus.ORDERED)
        self.assertIn(order, self.lab.pending_orders())
        self.technician.collect_sample(order)
        self.assertEqual(order.status, LabOrderStatus.SAMPLE_COLLECTED)
        self.technician.upload_result(order, self.aliyah, visit.visit_id,
                                      {"WBC": "13.2"}, "Raised WBC", is_abnormal=True)
        self.assertEqual(order.status, LabOrderStatus.COMPLETED)
        self.assertIs(order.patient, self.aliyah)
        self.assertIs(order.visit, visit)
        self.assertTrue(order.result.is_abnormal)
        self.assertNotIn(order, self.lab.pending_orders())

    def test_result_must_match_patient_and_visit(self):
        _, visit = self.book_and_start_visit()
        order = self.dr_brown.order_lab_test(visit, self.lab.get_test("FBC"), self.lab)
        other = self.clinic.register_patient("Sam", "Lee", date(1985, 5, 5), "1",
                                             "sam@example.com", None, "samlee", "Password#1")
        with self.assertRaises(ValidationError):
            self.technician.upload_result(order, other, visit.visit_id, {"WBC": "5"}, "ok")
        with self.assertRaises(ValidationError):
            self.technician.upload_result(order, self.aliyah, "VIS-9999", {"WBC": "5"}, "ok")
        self.assertEqual(order.status, LabOrderStatus.ORDERED)


# ====================================================================== #
class TestInvoiceAndPayment(ClinicTestBase):
    """(g) Generate invoice, apply insurance and process payment."""

    def _billable_visit(self):
        _, visit = self.book_and_start_visit()
        self.dr_brown.order_lab_test(visit, self.lab.get_test("FBC"), self.lab)
        self.dr_brown.prescribe(visit, [PrescriptionItem(
            self.pharmacy.get_medication("Amoxicillin"), "500 mg", "tds", 21)])
        visit.close()
        return visit

    def test_invoice_lines_and_insurance(self):
        invoice = self.clinic.billing.generate_invoice(self._billable_visit())
        # 80.00 consultation + 25.00 FBC + 21 x 0.80 amoxicillin = 121.80
        self.assertEqual(invoice.total, Decimal("121.80"))
        self.assertEqual(invoice.subtotal(ChargeCategory.CONSULTATION), Decimal("80.00"))
        self.assertEqual(invoice.subtotal(ChargeCategory.LAB), Decimal("25.00"))
        self.assertEqual(invoice.subtotal(ChargeCategory.MEDICATION), Decimal("16.80"))
        # (121.80 - 20 co-pay) x 80% = 81.44
        self.assertEqual(invoice.co_pay, Decimal("20.00"))
        self.assertEqual(invoice.insurer_share, Decimal("81.44"))
        self.assertEqual(invoice.patient_share, Decimal("40.36"))
        self.assertEqual(invoice.status, InvoiceStatus.UNPAID)

    def test_payment_process(self):
        invoice = self.clinic.billing.generate_invoice(self._billable_visit())
        InsuranceClaimPayment(invoice.insurer_share, self.policy).process(invoice)
        self.assertEqual(invoice.status, InvoiceStatus.PARTIALLY_PAID)
        card = CardPayment(invoice.patient_outstanding, "4111 1111 1111 1111",
                           "Aliyah Johnson", "12/30").process(invoice)
        self.assertEqual(card.status, PaymentStatus.SUCCESSFUL)
        self.assertEqual(invoice.balance_due, Decimal("0.00"))
        self.assertEqual(invoice.status, InvoiceStatus.PAID)
        self.assertEqual(self.policy.remaining_limit, Decimal("4918.56"))

    def test_rejected_payments(self):
        invoice = self.clinic.billing.generate_invoice(self._billable_visit())
        with self.assertRaises(PaymentError):              # fails Luhn check
            CardPayment(10, "4111 1111 1111 1112", "A J", "12/30").process(invoice)
        with self.assertRaises(PaymentError):              # more than the patient owes
            MobileWalletPayment(500, "Lynk", "+18765550199").process(invoice)
        with self.assertRaises(InvalidStateError):         # visit already invoiced
            self.clinic.billing.generate_invoice(invoice.visit)
        self.assertEqual(invoice.status, InvoiceStatus.UNPAID)

    def test_coverage_limits_and_expired_policy(self):
        self.policy.annual_limit = Decimal("50.00")
        invoice = self.clinic.billing.generate_invoice(self._billable_visit())
        self.assertEqual(invoice.insurer_share, Decimal("50.00"))   # capped at limit
        expired = InsurancePolicy("Old Insurer", "X-1", 90, 0, 1000, date(2020, 1, 1))
        with self.assertRaises(ValidationError):
            invoice.apply_insurance(expired)


# ====================================================================== #
class TestAppointmentCancellation(ClinicTestBase):
    """(h) Cancel an appointment."""

    def test_cancel_frees_slot(self):
        appt = self.clinic.scheduler.book(self.aliyah, self.dr_brown, self.at(10))
        self.clinic.scheduler.cancel(appt.appointment_id, "Feeling better")
        self.assertEqual(appt.status, AppointmentStatus.CANCELLED)
        self.assertEqual(appt.cancellation_reason, "Feeling better")
        self.assertEqual(self.aliyah.upcoming_appointments(self.clinic.scheduler), [])
        starts = [s.slot.start for s in
                  self.clinic.scheduler.search_available_slots(self.monday, doctor=self.dr_brown)]
        self.assertIn(self.at(10), starts)

    def test_cancelled_appointment_cannot_be_used(self):
        appt = self.clinic.scheduler.book(self.aliyah, self.dr_brown, self.at(10))
        self.clinic.scheduler.cancel(appt.appointment_id)
        with self.assertRaises(InvalidStateError):
            self.clinic.scheduler.cancel(appt.appointment_id)
        with self.assertRaises(InvalidStateError):
            self.clinic.scheduler.reschedule(appt.appointment_id, self.at(11))
        with self.assertRaises(InvalidStateError):
            self.dr_brown.start_visit(appt)


# ====================================================================== #
class TestExampleScenarios(ClinicTestBase):
    """Two complete end-to-end examples."""

    def test_example_1_aliyah_and_dr_brown(self):
        """Aliyah books 30 min next Monday with Dr. Brown (GP); full visit to payment."""
        # Patient and doctor exist
        self.assertEqual(self.dr_brown.full_name, "Dr. Michael Brown")
        self.assertEqual(self.dr_brown.speciality, "General Practice")

        # Booking a 30-minute appointment next Monday
        slot = self.clinic.scheduler.search_available_slots(
            self.monday, doctor=self.dr_brown)[0]
        appt = self.clinic.scheduler.book(self.aliyah, self.dr_brown, slot.slot.start, 30,
                                          "Sore throat and fever")
        self.assertEqual(appt.slot.start.weekday(), 0)
        self.assertEqual(appt.slot.duration_minutes, 30)

        # Visit: vitals, diagnosis, lab order, prescription
        visit = self.dr_brown.start_visit(appt)
        self.nurse.record_vitals(visit, Vitals(38.4, 122, 78, 96, 18, 64.5, 167))
        visit.add_diagnosis(Diagnosis("J02.9", "Acute pharyngitis", is_primary=True))
        order = self.dr_brown.order_lab_test(visit, self.lab.get_test("STREP"), self.lab)
        rx = self.dr_brown.prescribe(visit, [
            PrescriptionItem(self.pharmacy.get_medication("Amoxicillin"), "500 mg",
                             "1 capsule three times daily for 7 days", 21, 7),
            PrescriptionItem(self.pharmacy.get_medication("Paracetamol"), "1 g",
                             "2 tablets every 6 hours as needed", 20, 5)])
        rx.send_to_pharmacy(self.pharmacy)

        # Lab results uploaded
        self.technician.upload_result(order, self.aliyah, visit.visit_id,
                                      {"Strep A antigen": "Positive"},
                                      "Group A streptococcal pharyngitis", True)
        visit.close()

        # Invoice and payment
        invoice = self.clinic.billing.generate_invoice(visit)
        InsuranceClaimPayment(invoice.insurer_share, self.policy).process(invoice)
        CardPayment(invoice.patient_outstanding, "5555 5555 5555 4444",
                    "Aliyah Johnson", "08/29").process(invoice)

        # Assertions: visit data, prescription and billing are accurate
        self.assertEqual(appt.status, AppointmentStatus.COMPLETED)
        self.assertEqual(visit.diagnoses[0].description, "Acute pharyngitis")
        self.assertEqual(visit.vitals.blood_pressure, "122/78 mmHg")
        self.assertEqual(order.status, LabOrderStatus.COMPLETED)
        self.assertEqual(rx.status, PrescriptionStatus.SENT_TO_PHARMACY)
        self.assertEqual([i.drug_name for i in rx.items], ["Amoxicillin", "Paracetamol"])
        # 80 + 18 + 16.80 + 2.00 = 116.80; insurer (116.80 - 20) x 0.8 = 77.44
        self.assertEqual(invoice.total, Decimal("116.80"))
        self.assertEqual(invoice.insurer_share, Decimal("77.44"))
        self.assertEqual(invoice.patient_share, Decimal("39.36"))
        self.assertEqual(invoice.status, InvoiceStatus.PAID)

    def test_example_2_uninsured_cardiology_patient(self):
        """Marcus (no insurance) is rescheduled, seen by Dr. Okafor and pays by wallet."""
        marcus = self.clinic.register_patient(
            "Marcus", "Grant", date(1962, 2, 14), "+1 876 555 0400",
            "marcus.grant@example.com", None, "mgrant", "Heart#Health1",
            medical_history_summary="Hypertension, family history of heart disease")
        wednesday = self.monday + timedelta(days=2)
        appt = self.clinic.scheduler.book(marcus, self.dr_okafor,
                                          self.at(13, 0, wednesday), 30, "Chest tightness")
        self.clinic.scheduler.reschedule(appt.appointment_id, self.at(14, 30, wednesday))
        self.assertEqual(appt.status, AppointmentStatus.RESCHEDULED)

        visit = self.dr_okafor.start_visit(appt)
        self.nurse.record_vitals(visit, Vitals(36.8, 148, 94, 82, 16, 92, 178))
        visit.add_diagnosis(Diagnosis("I10", "Essential hypertension", is_primary=True))
        visit.add_diagnosis(Diagnosis("E78.5", "Hyperlipidaemia"))
        order = self.dr_okafor.order_lab_test(visit, self.lab.get_test("LIPID"), self.lab)
        rx = self.dr_okafor.prescribe(visit, [PrescriptionItem(
            self.pharmacy.get_medication("Atorvastatin"), "20 mg",
            "1 tablet at night", 30, 30)])
        rx.send_to_pharmacy(self.pharmacy)
        self.pharmacist.dispense(rx)
        self.technician.upload_result(order, marcus, visit.visit_id,
                                      {"LDL": "4.6 mmol/L", "HDL": "1.0 mmol/L"},
                                      "Raised LDL cholesterol", True)
        visit.close()

        invoice = self.clinic.billing.generate_invoice(visit)
        # 150 consultation + 40 lipid panel + 30 x 0.50 atorvastatin = 205.00
        self.assertEqual(invoice.total, Decimal("205.00"))
        self.assertEqual(invoice.insurer_share, Decimal("0.00"))
        self.assertEqual(invoice.patient_share, Decimal("205.00"))
        MobileWalletPayment(205, "Lynk", "+1 876 555 0400").process(invoice)

        self.assertEqual(invoice.status, InvoiceStatus.PAID)
        self.assertEqual(rx.status, PrescriptionStatus.DISPENSED)
        self.assertEqual(order.result.values["LDL"], "4.6 mmol/L")
        self.assertEqual(len(marcus.medical_record.visits(marcus)), 1)
        self.assertEqual(visit.vitals.bmi, 29.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
