"""
sample_data.py
==============
Builds a fully configured Royal Care Clinic (departments, staff, lab test
catalogue and pharmacy formulary). Shared by ``main.py`` and the tests so
both work with the same, realistic set-up.
"""

from datetime import date

from .clinic import Address, Clinic, ContactInfo, Department, Laboratory, Pharmacy
from .hours import WeeklyHours
from .lab import LabTest
from .people import Doctor, LabTechnician, Nurse, Pharmacist
from .prescriptions import Medication


def build_royal_care_clinic() -> Clinic:
    """Create and return the Royal Care Clinic with sample departments and staff."""
    clinic = Clinic(
        name="Royal Care Clinic",
        address=Address("14 Harbour View Road", "Kingston", "Jamaica", "KN10"),
        contact=ContactInfo(["+1 876 555 0100", "+1 876 555 0101"],
                            "info@royalcareclinic.example",
                            "www.royalcareclinic.example"),
    )

    # ---------------------------- departments ---------------------------- #
    saturday_hours = WeeklyHours.weekdays("08:00", "18:00")
    saturday_hours.set_day(5, "09:00", "13:00")
    clinic.add_department(Department("General Practice", "Primary care consultations",
                                     "Ground floor, Wing A", "ext. 201", saturday_hours))
    clinic.add_department(Department("Cardiology", "Heart and circulation",
                                     "First floor, Wing B", "ext. 305"))
    clinic.add_department(Department("Paediatrics", "Care for children and adolescents",
                                     "Ground floor, Wing C", "ext. 220"))
    clinic.add_department(Department("Radiology", "X-ray and ultrasound imaging",
                                     "Basement", "ext. 110"))
    lab = clinic.add_department(Laboratory(description="Pathology and blood tests",
                                           location="Basement", phone="ext. 115"))
    pharmacy = clinic.add_department(Pharmacy(description="Outpatient dispensary",
                                              location="Ground floor, Lobby",
                                              phone="ext. 100"))

    # ------------------------------ doctors ------------------------------ #
    clinic.add_staff(Doctor("Michael", "Brown", date(1978, 4, 12), "+1 876 555 0110",
                            "m.brown@royalcareclinic.example", "General Practice",
                            "MD-GP-1042", 80, ["MBBS", "DFM"],
                            WeeklyHours.weekdays("09:00", "12:00")),
                     "General Practice")
    clinic.add_staff(Doctor("Ngozi", "Okafor", date(1981, 9, 3), "+1 876 555 0111",
                            "n.okafor@royalcareclinic.example", "Cardiology",
                            "MD-CA-2210", 150, ["MBBS", "MRCP", "FACC"],
                            WeeklyHours.weekdays("13:00", "16:00")),
                     "Cardiology")
    clinic.add_staff(Doctor("Ravi", "Patel", date(1985, 1, 22), "+1 876 555 0112",
                            "r.patel@royalcareclinic.example", "Paediatrics",
                            "MD-PD-3307", 95, ["MBBS", "DCH"],
                            WeeklyHours.weekdays("09:00", "15:00")),
                     "Paediatrics")

    # ---------------------------- other staff ---------------------------- #
    clinic.add_staff(Nurse("Grace", "Thompson", date(1990, 6, 14), "+1 876 555 0120",
                           "g.thompson@royalcareclinic.example",
                           qualifications=["RN", "BSc Nursing"]), "General Practice")
    clinic.add_staff(LabTechnician("Daniel", "Reid", date(1992, 11, 30), "+1 876 555 0130",
                                   "d.reid@royalcareclinic.example",
                                   qualifications=["BSc Medical Technology"]), "Laboratory")
    clinic.add_staff(Pharmacist("Sophia", "Campbell", date(1988, 2, 8), "+1 876 555 0140",
                                "s.campbell@royalcareclinic.example",
                                qualifications=["BPharm"]), "Pharmacy")

    # ------------------------- catalogues ------------------------------- #
    for test in (LabTest("FBC", "Full Blood Count", "Blood", 25),
                 LabTest("LIPID", "Lipid Panel", "Blood", 40),
                 LabTest("HBA1C", "HbA1c (Glycated Haemoglobin)", "Blood", 35),
                 LabTest("URINE", "Urinalysis", "Urine", 15),
                 LabTest("STREP", "Rapid Strep A Test", "Throat swab", 18, 1)):
        lab.add_test(test)

    for med in (Medication("Amoxicillin", "500 mg", "capsule", 0.80),
                Medication("Paracetamol", "500 mg", "tablet", 0.10),
                Medication("Ibuprofen", "400 mg", "tablet", 0.15),
                Medication("Atorvastatin", "20 mg", "tablet", 0.50),
                Medication("Penicillin V", "250 mg", "tablet", 0.30)):
        pharmacy.add_medication(med)

    return clinic
