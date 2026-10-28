# Royal Care Clinic – Healthcare Clinic Management System

An object-oriented Python application for an outpatient clinic. It manages
the clinic profile and departments, patients, doctors and staff, appointment
scheduling, electronic medical records (EMR), prescriptions, laboratory orders,
and billing with insurance and co-pay calculation.

The code uses only the Python standard library (Python 3.10 or newer).

## Project structure

```
royal-care-clinic/
├── royal_care/               # application package
│   ├── enums.py              # status / role enumerations
│   ├── exceptions.py         # custom exception hierarchy
│   ├── utils.py              # ID generator, money helpers, dates
│   ├── hours.py              # WeeklyHours (operating / working hours)
│   ├── clinic.py             # Clinic, Department, Laboratory, Pharmacy, ...
│   ├── people.py             # Person, Patient, Staff, Doctor, Nurse, ...
│   ├── accounts.py           # UserAccount (patient login)
│   ├── scheduling.py         # TimeSlot, Appointment, AppointmentScheduler
│   ├── emr.py                # MedicalRecord, Visit, Vitals, Diagnosis, ...
│   ├── prescriptions.py      # Medication, Prescription, PrescriptionItem
│   ├── lab.py                # LabTest, LabOrder, LabResult
│   ├── billing.py            # Invoice, InsurancePolicy, Payment subclasses
│   ├── formatting.py         # console output helpers
│   └── sample_data.py        # builds the sample Royal Care Clinic
├── tests/
│   └── test_clinic_system.py # unit + scenario tests
├── docs/
│   ├── uml_class_diagram.puml # UML source (PlantUML)
│   ├── uml_class_diagram.png  # rendered diagram
│   └── uml_class_diagram.svg  # scalable version
└── main.py                   # end-to-end demonstration
```

## Running

```bash
python main.py                                   # run the demonstration
python -m unittest discover -s tests -v          # run all tests
```

## Regenerating the UML diagram

```bash
java -jar plantuml.jar -tpng docs/uml_class_diagram.puml
```

## Features

| Area | What it does |
|------|--------------|
| Clinic information | Profile, contact details, departments with operating hours (add / update / retrieve) |
| Patients | Self-registration with hashed password, profile updates, allergies, insurance, visit-summary download |
| Doctors & staff | Doctor, Nurse, Lab Technician and Pharmacist roles with qualifications and working hours |
| Scheduling | Search free slots by date, doctor or speciality; book, reschedule and cancel |
| EMR | Visits with notes, vitals, diagnoses, attachments, prescriptions and lab orders; access control |
| Prescriptions | Drug, dosage and directions; allergy check; sent to pharmacy and dispensed |
| Laboratory | Order lifecycle ORDERED -> SAMPLE_COLLECTED -> COMPLETED; results checked against patient and visit |
| Billing | Invoice per visit, insurance coverage with co-pay and annual limit, card / mobile wallet / insurance claim payments |
