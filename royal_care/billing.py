"""
billing.py
==========
Billing, insurance and payments.

* ``InsurancePolicy`` - coverage percentage, flat co-pay and annual limit.
* ``InvoiceLineItem`` - one charge on an invoice.
* ``Invoice``         - *composition* of line items and *aggregation* of
  payments; generated per visit.
* ``Payment`` (abstract) with subclasses ``CardPayment``,
  ``MobileWalletPayment`` and ``InsuranceClaimPayment`` (inheritance and
  polymorphism: each subclass authorises the payment in its own way).
* ``BillingService``  - builds an invoice from everything done in a visit.

Insurance / co-pay rule used
----------------------------
1. ``eligible``  = sum of charges in categories the policy covers.
2. ``co_pay``    = the policy's flat co-pay (never more than ``eligible``).
3. ``insurer``   = (eligible - co_pay) x coverage %, capped at the policy's
   remaining annual limit.
4. ``patient``   = invoice total - insurer share.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Iterable, List, Optional, Set

from .enums import ChargeCategory, InvoiceStatus, LabOrderStatus, PaymentStatus
from .exceptions import InvalidStateError, PaymentError, ValidationError
from .utils import IdGenerator, format_money, to_money

if TYPE_CHECKING:
    from .emr import Visit
    from .people import Patient

ZERO = Decimal("0.00")


# ====================================================================== #
# Insurance
# ====================================================================== #
class InsurancePolicy:
    """A patient's health insurance policy."""

    def __init__(self, provider: str, policy_number: str, coverage_percent: float,
                 co_pay, annual_limit, valid_until: date,
                 covered_categories: Optional[Iterable[ChargeCategory]] = None) -> None:
        if not 0 <= coverage_percent <= 100:
            raise ValidationError("Coverage percent must be between 0 and 100.")
        self.provider = provider
        self._policy_number = policy_number
        self.coverage_percent = Decimal(str(coverage_percent))
        self.co_pay = to_money(co_pay)
        self.annual_limit = to_money(annual_limit)
        self.valid_until = valid_until
        self.covered_categories: Set[ChargeCategory] = set(
            covered_categories or list(ChargeCategory))
        self._claimed_to_date = ZERO

    @property
    def policy_number(self) -> str:
        return self._policy_number

    @property
    def remaining_limit(self) -> Decimal:
        return to_money(self.annual_limit - self._claimed_to_date)

    def is_valid(self, on: Optional[date] = None) -> bool:
        return (on or date.today()) <= self.valid_until

    def covers(self, category: ChargeCategory) -> bool:
        return category in self.covered_categories

    def record_claim(self, amount: Decimal) -> None:
        """Reduce the remaining annual limit after a paid claim."""
        if amount > self.remaining_limit:
            raise PaymentError("Claim exceeds the remaining annual limit.")
        self._claimed_to_date = to_money(self._claimed_to_date + amount)

    def __str__(self) -> str:
        return (f"{self.provider} #{self._policy_number} - {self.coverage_percent}% "
                f"cover, co-pay {format_money(self.co_pay)}")


# ====================================================================== #
# Invoice
# ====================================================================== #
class InvoiceLineItem:
    """A single charge on an invoice."""

    def __init__(self, description: str, category: ChargeCategory,
                 quantity: int, unit_price) -> None:
        if quantity <= 0:
            raise ValidationError("Quantity must be positive.")
        self.description = description
        self.category = category
        self.quantity = quantity
        self.unit_price = to_money(unit_price)

    @property
    def total(self) -> Decimal:
        return to_money(self.unit_price * self.quantity)


class Invoice:
    """An invoice for one visit."""

    def __init__(self, visit: Visit) -> None:
        self._invoice_id = IdGenerator.next_id("INV")
        self._visit = visit
        self.issued_at = datetime.now()
        self._items: List[InvoiceLineItem] = []      # composition
        self._payments: List[Payment] = []           # aggregation
        self.policy: Optional[InsurancePolicy] = None
        self._insurer_share = ZERO
        self._co_pay = ZERO

    # ---- basic properties ---- #
    @property
    def invoice_id(self) -> str:
        return self._invoice_id

    @property
    def visit(self) -> Visit:
        return self._visit

    @property
    def patient(self) -> Patient:
        return self._visit.patient

    @property
    def items(self) -> List[InvoiceLineItem]:
        return list(self._items)

    @property
    def payments(self) -> List[Payment]:
        return list(self._payments)

    def add_item(self, item: InvoiceLineItem) -> None:
        if self._payments:
            raise InvalidStateError("Cannot add charges after payments have been taken.")
        self._items.append(item)
        if self.policy:                       # keep insurance figures up to date
            self.apply_insurance(self.policy)

    # ---- totals ---- #
    @property
    def total(self) -> Decimal:
        return to_money(sum((i.total for i in self._items), ZERO))

    def subtotal(self, category: ChargeCategory) -> Decimal:
        return to_money(sum((i.total for i in self._items if i.category is category), ZERO))

    @property
    def insurer_share(self) -> Decimal:
        return self._insurer_share

    @property
    def co_pay(self) -> Decimal:
        return self._co_pay

    @property
    def patient_share(self) -> Decimal:
        return to_money(self.total - self._insurer_share)

    def _paid(self, insurer: bool) -> Decimal:
        return to_money(sum((p.amount for p in self._payments
                             if p.status is PaymentStatus.SUCCESSFUL
                             and isinstance(p, InsuranceClaimPayment) == insurer), ZERO))

    @property
    def patient_outstanding(self) -> Decimal:
        return to_money(self.patient_share - self._paid(insurer=False))

    @property
    def insurer_outstanding(self) -> Decimal:
        return to_money(self._insurer_share - self._paid(insurer=True))

    @property
    def balance_due(self) -> Decimal:
        return to_money(self.patient_outstanding + self.insurer_outstanding)

    @property
    def status(self) -> InvoiceStatus:
        if self.balance_due == ZERO and self.total > ZERO:
            return InvoiceStatus.PAID
        if any(p.status is PaymentStatus.SUCCESSFUL for p in self._payments):
            return InvoiceStatus.PARTIALLY_PAID
        return InvoiceStatus.UNPAID

    # ---- insurance ---- #
    def apply_insurance(self, policy: InsurancePolicy,
                        on: Optional[date] = None) -> Decimal:
        """Calculate the insurer's share and co-pay; returns the insurer share."""
        if self._payments:
            raise InvalidStateError("Insurance must be applied before payments are taken.")
        if not policy.is_valid(on):
            raise ValidationError(f"Insurance policy {policy.policy_number} has expired.")
        eligible = to_money(sum((i.total for i in self._items
                                 if policy.covers(i.category)), ZERO))
        self._co_pay = min(policy.co_pay, eligible)
        claimable = to_money((eligible - self._co_pay) * policy.coverage_percent / 100)
        self._insurer_share = min(claimable, policy.remaining_limit)
        self.policy = policy
        return self._insurer_share

    # ---- payments ---- #
    def _register_payment(self, payment: Payment) -> None:
        """Called by ``Payment.process`` after a successful authorisation."""
        self._payments.append(payment)

    def __str__(self) -> str:
        return (f"{self._invoice_id} ({self.patient.full_name}) total "
                f"{format_money(self.total)} [{self.status.value}]")


# ====================================================================== #
# Payments (abstract base + concrete methods)
# ====================================================================== #
class Payment(ABC):
    """Abstract payment. Subclasses implement :meth:`_authorise`.

    :meth:`process` is a *template method*: the shared steps (validation,
    recording on the invoice) are written once here, while the
    method-specific authorisation step is supplied by each subclass.
    """

    def __init__(self, amount) -> None:
        self._payment_id = IdGenerator.next_id("PAY")
        self._amount = to_money(amount)
        if self._amount <= ZERO:
            raise ValidationError("Payment amount must be positive.")
        self._status = PaymentStatus.PENDING
        self.paid_at: Optional[datetime] = None
        self.reference: Optional[str] = None

    @property
    def payment_id(self) -> str:
        return self._payment_id

    @property
    def amount(self) -> Decimal:
        return self._amount

    @property
    def status(self) -> PaymentStatus:
        return self._status

    @property
    @abstractmethod
    def method_name(self) -> str:
        """Display name of the payment method."""

    @abstractmethod
    def _authorise(self, invoice: Invoice) -> str:
        """Authorise the payment and return a reference; raise PaymentError if refused."""

    def _outstanding(self, invoice: Invoice) -> Decimal:
        """The part of the invoice this payment type is allowed to settle."""
        return invoice.patient_outstanding

    def process(self, invoice: Invoice) -> "Payment":
        """Validate, authorise and record the payment against ``invoice``."""
        if self._status is not PaymentStatus.PENDING:
            raise InvalidStateError("This payment has already been processed.")
        outstanding = self._outstanding(invoice)
        if self._amount > outstanding:
            self._status = PaymentStatus.FAILED
            raise PaymentError(
                f"{self.method_name} payment of {format_money(self._amount)} exceeds "
                f"the amount due ({format_money(outstanding)}).")
        try:
            self.reference = self._authorise(invoice)
        except PaymentError:
            self._status = PaymentStatus.FAILED
            raise
        self._status = PaymentStatus.SUCCESSFUL
        self.paid_at = datetime.now()
        invoice._register_payment(self)
        return self

    def __str__(self) -> str:
        return (f"{self._payment_id} {self.method_name} {format_money(self._amount)} "
                f"[{self._status.value}]")


class CardPayment(Payment):
    """Payment by debit/credit card (number checked with the Luhn algorithm)."""

    def __init__(self, amount, card_number: str, card_holder: str, expiry: str) -> None:
        super().__init__(amount)
        digits = card_number.replace(" ", "")
        if not digits.isdigit() or not 12 <= len(digits) <= 19:
            raise ValidationError("Card number must contain 12-19 digits.")
        self._card_number = digits          # kept private, only masked form is shown
        self.card_holder = card_holder
        self.expiry = expiry                # "MM/YY"

    @property
    def method_name(self) -> str:
        return "Card"

    @property
    def masked_number(self) -> str:
        return "**** **** **** " + self._card_number[-4:]

    @staticmethod
    def luhn_valid(number: str) -> bool:
        """Standard Luhn checksum used by card networks."""
        total = 0
        for i, ch in enumerate(reversed(number)):
            d = int(ch)
            if i % 2 == 1:
                d = d * 2 - 9 if d > 4 else d * 2
            total += d
        return total % 10 == 0

    def _is_expired(self) -> bool:
        month, year = self.expiry.split("/")
        expiry_key = (2000 + int(year), int(month))
        today = date.today()
        return expiry_key < (today.year, today.month)

    def _authorise(self, invoice: Invoice) -> str:
        if not self.luhn_valid(self._card_number):
            raise PaymentError("Card declined: invalid card number.")
        if self._is_expired():
            raise PaymentError("Card declined: card has expired.")
        return f"CARD-AUTH-{self._card_number[-4:]}-{self.payment_id}"


class MobileWalletPayment(Payment):
    """Payment through a mobile wallet (e.g. Apple Pay, M-Pesa)."""

    def __init__(self, amount, provider: str, phone_number: str) -> None:
        super().__init__(amount)
        if not phone_number.replace("+", "").replace(" ", "").isdigit():
            raise ValidationError("Wallet phone number must contain digits only.")
        self.provider = provider
        self.phone_number = phone_number

    @property
    def method_name(self) -> str:
        return f"Mobile Wallet ({self.provider})"

    def _authorise(self, invoice: Invoice) -> str:
        return f"WALLET-{self.provider.upper().replace(' ', '')}-{self.payment_id}"


class InsuranceClaimPayment(Payment):
    """Settlement of the insurer's share through an insurance claim."""

    def __init__(self, amount, policy: InsurancePolicy) -> None:
        super().__init__(amount)
        self.policy = policy
        self.claim_number = IdGenerator.next_id("CLM")

    @property
    def method_name(self) -> str:
        return f"Insurance Claim ({self.policy.provider})"

    def _outstanding(self, invoice: Invoice) -> Decimal:
        return invoice.insurer_outstanding

    def _authorise(self, invoice: Invoice) -> str:
        if invoice.policy is not self.policy:
            raise PaymentError("Insurance has not been applied to this invoice with this policy.")
        self.policy.record_claim(self.amount)
        return self.claim_number


# ====================================================================== #
# Billing service
# ====================================================================== #
class BillingService:
    """Generates invoices for visits and keeps them for lookup."""

    def __init__(self) -> None:
        self._invoices: dict[str, Invoice] = {}

    def generate_invoice(self, visit: Visit,
                         other_services: Optional[List[InvoiceLineItem]] = None,
                         apply_patient_insurance: bool = True) -> Invoice:
        """Create an invoice containing consultation, lab, medication and other charges.

        If the patient has a valid insurance policy it is applied automatically.
        """
        if any(inv.visit is visit for inv in self._invoices.values()):
            raise InvalidStateError(f"Visit {visit.visit_id} has already been invoiced.")
        invoice = Invoice(visit)
        doctor = visit.doctor
        invoice.add_item(InvoiceLineItem(
            f"Consultation - {doctor.full_name} ({doctor.speciality})",
            ChargeCategory.CONSULTATION, 1, doctor.consultation_fee))
        for order in visit.lab_orders:
            if order.status is not LabOrderStatus.CANCELLED:
                invoice.add_item(InvoiceLineItem(
                    f"Lab test - {order.test.name}", ChargeCategory.LAB, 1, order.test.price))
        for prescription in visit.prescriptions:
            for item in prescription.items:
                invoice.add_item(InvoiceLineItem(
                    f"Medication - {item.medication}", ChargeCategory.MEDICATION,
                    item.quantity, item.medication.unit_price))
        for service in other_services or []:
            invoice.add_item(service)

        policy = visit.patient.insurance
        if apply_patient_insurance and policy is not None and policy.is_valid():
            invoice.apply_insurance(policy)
        self._invoices[invoice.invoice_id] = invoice
        return invoice

    def get_invoice(self, invoice_id: str) -> Invoice:
        return self._invoices[invoice_id]

    @property
    def invoices(self) -> List[Invoice]:
        return list(self._invoices.values())
