"""
main.py
=======
End-to-end demonstration of the Royal Care Clinic Management System.

Scenario (from the assignment brief)
------------------------------------
1. Create patient Aliyah and doctor Dr. Brown (General Practitioner).
2. Aliyah searches for and books a 30-minute appointment next Monday.
3. The doctor conducts the visit, records vitals and a diagnosis, orders a
   lab test and issues a prescription (sent to the pharmacy).
4. Lab results are uploaded, the invoice is generated with insurance
   applied, and payment is completed.

The script also shows rescheduling, cancellation, access control and the
patient downloading a visit summary.

Run with:  python main.py
"""

from datetime import date, datetime, time, timedelta

from royal_care import (AccessDeniedError, Attachment, ChargeCategory, CardPayment,
                        Diagnosis, EmergencyContact, InsuranceClaimPayment,
                        InsurancePolicy, InvoiceLineItem, LabTechnician,
                        MobileWalletPayment, Nurse, Pharmacist, PrescriptionItem,
                        ValidationError, Vitals)
from royal_care.clinic import Address
from royal_care.formatting import heading, key_values, subheading, table
from royal_care.sample_data import build_royal_care_clinic
from royal_care.utils import format_money, next_weekday, to_money


def main() -> None:
    clinic = build_royal_care_clinic()

    # ================================================================== #
    # 1. Clinic information
    # ================================================================== #
    print(heading("Royal Care Clinic Management System"))
    info = clinic.get_info()
    print(subheading("Clinic profile"))
    print(key_values([("Name", info["name"]), ("Address", info["address"]),
                      ("Phone", ", ".join(info["phone_numbers"])),
                      ("Email", info["email"]), ("Website", info["website"])]))

    print(subheading("Departments"))
    print(table(["Department", "Type", "Location", "Mon hours", "Sat hours", "Staff"],
                [[d.name, type(d).__name__, d.location,
                  d.operating_hours.describe()[0].split(": ")[1],
                  d.operating_hours.describe()[5].split(": ")[1], len(d.staff)]
                 for d in clinic.departments]))

    clinic.update_department("Radiology", phone="ext. 111")
    print("\n  Updated Radiology phone ->", clinic.get_department("Radiology").phone)

    print(subheading("Doctors"))
    print(table(["ID", "Name", "Speciality", "Qualifications", "Fee"],
                [[d.person_id, d.full_name, d.speciality, ", ".join(d.qualifications),
                  format_money(d.consultation_fee)] for d in clinic.doctors()],
                align_right=[4]))

    # ================================================================== #
    # 2. Patient account creation
    # ================================================================== #
    print(heading("Patient registration"))
    insurance = InsurancePolicy("Sagicor Health", "SH-778812", coverage_percent=80,
                                co_pay=20, annual_limit=5000,
                                valid_until=date.today() + timedelta(days=365))
    aliyah = clinic.register_patient(
        "Aliyah", "Johnson", date(1996, 7, 19), "+1 876 555 0199",
        "aliyah.johnson@example.com",
        Address("27 Palm Avenue", "Kingston", "Jamaica", "KN5"),
        username="aliyahj", password="Secure#2026",
        emergency_contact=EmergencyContact("Marcus Johnson", "Brother", "+1 876 555 0177"),
        insurance=insurance, allergies=["Penicillin V"],
        medical_history_summary="Mild asthma (childhood); no surgeries.")
    logged_in = clinic.login("aliyahj", "Secure#2026")
    print(key_values([("Patient ID", aliyah.person_id), ("Name", aliyah.full_name),
                      ("Age", aliyah.age()), ("Email", aliyah.email),
                      ("Emergency contact", aliyah.emergency_contact),
                      ("Insurance", aliyah.insurance),
                      ("Allergies", ", ".join(aliyah.allergies)),
                      ("History", aliyah.medical_history_summary),
                      ("Login check", "OK" if logged_in is aliyah else "FAILED")]))
    aliyah.update_profile(phone="+1 876 555 0200")
    print(f"\n  Profile updated: new phone {aliyah.phone}")

    # ================================================================== #
    # 3. Search and book an appointment
    # ================================================================== #
    print(heading("Appointment scheduling"))
    dr_brown = clinic.doctors("General Practice")[0]
    monday = next_weekday(date.today(), 0)
    slots = clinic.scheduler.search_available_slots(monday, speciality="General Practice")
    print(subheading(f"Available GP slots on {monday:%A %d %B %Y}"))
    print(table(["#", "Doctor", "Slot"],
                [[i + 1, s.doctor.full_name, str(s.slot)] for i, s in enumerate(slots)]))

    appointment = clinic.scheduler.book(aliyah, dr_brown, datetime.combine(monday, time(9, 30)),
                                        30, reason="Sore throat and fever for 3 days")
    print(f"\n  Booked   : {appointment}")
    clinic.scheduler.reschedule(appointment.appointment_id,
                                datetime.combine(monday, time(10, 0)))
    print(f"  Moved    : {appointment}")

    # A second appointment that the patient later cancels
    dr_okafor = clinic.doctors("Cardiology")[0]
    follow_up = clinic.scheduler.book(aliyah, dr_okafor,
                                      datetime.combine(monday + timedelta(days=2), time(14, 0)),
                                      reason="Palpitations review")
    clinic.scheduler.cancel(follow_up.appointment_id, "Symptoms resolved")
    print(f"  Cancelled: {follow_up}")

    print(subheading("Aliyah's upcoming appointments (patient portal)"))
    for appt in aliyah.upcoming_appointments(clinic.scheduler):
        print(f"  {appt}")

    # ================================================================== #
    # 4. The visit (EMR)
    # ================================================================== #
    print(heading("Visit and electronic medical record"))
    nurse = next(s for s in clinic.get_department("General Practice").staff
                 if isinstance(s, Nurse))
    lab = clinic.laboratory()
    pharmacy = clinic.pharmacy()

    visit = dr_brown.start_visit(appointment)
    nurse.record_vitals(visit, Vitals(38.4, 122, 78, 96, 18, 64.5, 167, 97))
    visit.add_note("Erythematous pharynx with tonsillar exudate; no cough.", dr_brown)
    visit.add_diagnosis(Diagnosis("J02.9", "Acute pharyngitis, unspecified", is_primary=True))
    visit.add_attachment(Attachment("referral_letter.pdf", b"%PDF-1.4 scanned referral",
                                    description="Scanned referral from employer clinic"))

    lab_order = dr_brown.order_lab_test(visit, lab.get_test("FBC"), lab,
                                        notes="Check white cell count")
    prescription = dr_brown.prescribe(visit, [
        PrescriptionItem(pharmacy.get_medication("Amoxicillin"), "500 mg",
                         "1 capsule three times daily for 7 days", 21, 7),
        PrescriptionItem(pharmacy.get_medication("Paracetamol"), "1 g",
                         "2 tablets every 6 hours as needed for fever", 20, 5),
    ])
    prescription.send_to_pharmacy(pharmacy)
    print(key_values([("Visit", visit.visit_id), ("Vitals", visit.vitals),
                      ("Diagnosis", visit.diagnoses[0]),
                      ("Lab order", lab_order), ("Prescription", prescription)]))

    # The prescriber cannot give Aliyah the drug she is allergic to
    try:
        dr_brown.prescribe(visit, [PrescriptionItem(
            pharmacy.get_medication("Penicillin V"), "250 mg", "four times daily", 28)])
    except ValidationError as error:
        print(f"\n  Allergy check blocked prescription: {error}")

    # ================================================================== #
    # 5. Lab results and dispensing
    # ================================================================== #
    print(heading("Laboratory results and pharmacy"))
    technician = next(s for s in lab.staff if isinstance(s, LabTechnician))
    technician.collect_sample(lab_order)
    print(f"  Sample collected  -> {lab_order.status.value}")
    technician.upload_result(lab_order, aliyah, visit.visit_id,
                             {"WBC": "13.2 x10^9/L", "Neutrophils": "82 %", "Hb": "13.1 g/dL"},
                             "Neutrophilic leucocytosis consistent with bacterial infection",
                             is_abnormal=True)
    print(f"  Result uploaded   -> {lab_order.status.value}")
    print(f"  Result            : {lab_order.result}")

    pharmacist = next(s for s in pharmacy.staff if isinstance(s, Pharmacist))
    pharmacist.dispense(prescription)
    print(f"  Prescription      -> {prescription.status.value} by {pharmacist.full_name}")

    visit.close()
    print(f"  Appointment       -> {appointment.status.value}")

    # ================================================================== #
    # 6. Billing and payment
    # ================================================================== #
    print(heading("Billing and payment"))
    invoice = clinic.billing.generate_invoice(visit, other_services=[
        InvoiceLineItem("Nebuliser use", ChargeCategory.OTHER, 1, 12)])
    print(table(["Description", "Category", "Qty", "Unit", "Total"],
                [[i.description, i.category.value, i.quantity,
                  format_money(i.unit_price), format_money(i.total)]
                 for i in invoice.items], align_right=[2, 3, 4]))
    print()
    print(key_values([("Invoice", invoice.invoice_id),
                      ("Total charges", format_money(invoice.total)),
                      ("Insurance", invoice.policy),
                      ("Co-pay", format_money(invoice.co_pay)),
                      ("Insurer pays", format_money(invoice.insurer_share)),
                      ("Patient pays", format_money(invoice.patient_share)),
                      ("Status", invoice.status.value)]))

    claim = InsuranceClaimPayment(invoice.insurer_share, insurance).process(invoice)
    half = to_money(invoice.patient_share / 2)       # split between wallet and card
    wallet = MobileWalletPayment(half, "Lynk", "+1 876 555 0200").process(invoice)
    card = CardPayment(invoice.patient_outstanding, "4111 1111 1111 1111",
                       "Aliyah Johnson", "12/29").process(invoice)
    print(subheading("Payments"))
    print(table(["Payment", "Method", "Amount", "Reference", "Status"],
                [[p.payment_id, p.method_name, format_money(p.amount), p.reference,
                  p.status.value] for p in (claim, wallet, card)], align_right=[2]))
    print(f"\n  Balance due: {format_money(invoice.balance_due)} -> "
          f"invoice {invoice.status.value}")
    print(f"  Insurance limit remaining: {format_money(insurance.remaining_limit)}")

    # ================================================================== #
    # 7. Access control and visit summary download
    # ================================================================== #
    print(heading("Access control and visit summary"))
    other = clinic.register_patient("Jordan", "Clarke", date(1990, 3, 2), "+1 876 555 0300",
                                    "jordan.clarke@example.com", None, "jclarke", "Another#Pass1")
    try:
        aliyah.medical_record.get_visit(visit.visit_id, requester=other)
    except AccessDeniedError as error:
        print(f"  Other patient denied : {error}")
    seen = aliyah.medical_record.get_visit(visit.visit_id, requester=dr_brown)
    print(f"  Doctor access granted: {seen.visit_id}")

    path = aliyah.download_visit_summary(visit.visit_id)
    print(f"  Summary downloaded to: {path}\n")
    print(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
