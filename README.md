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
│   ├── clinic.py             # Clinic, Department, Laboratory, Pharmacy, ...
│   ├── people.py             # Person, Patient, Staff, Doctor, Nurse, ...
│   ├── accounts.py           # UserAccount (patient login)
│   ├── scheduling.py         # TimeSlot, Appointment, AppointmentScheduler
│   ├── emr.py                # MedicalRecord, Visit, Vitals, Diagnosis, ...
│   ├── prescriptions.py      # Medication, Prescription, PrescriptionItem
│   ├── lab.py                # LabTest, LabOrder, LabResult
│   ├── billing.py            # Invoice, InsurancePolicy, Payment subclasses
│   └── formatting.py         # console output helpers
├── tests/
│   └── test_clinic_system.py # unit + scenario tests
├── docs/
│   ├── uml_class_diagram.mmd # UML source (Mermaid)
│   └── uml_class_diagram.png # rendered diagram
└── main.py                   # end-to-end demonstration
```

## Running

```bash
python main.py                                   # run the demonstration
python -m unittest discover -s tests -v          # run all tests
```
