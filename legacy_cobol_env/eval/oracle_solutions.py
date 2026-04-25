"""Deterministic reference candidate solutions for sanity and demo traces."""

from __future__ import annotations

from legacy_cobol_env.server.task_bank import TaskInstance


PAYROLL_SOLUTION = r'''
from decimal import Decimal, ROUND_HALF_UP


def migrate(input_record: str) -> str:
    emp_id = input_record[0:6]
    emp_name = input_record[6:18]
    gross = Decimal(int(input_record[18:27])) / Decimal("100")
    tax_rate = Decimal(int(input_record[27:31])) / Decimal("1000")
    raw_deductions = input_record[31:39]
    sign = -1 if raw_deductions[0] == "-" else 1
    deductions = Decimal(sign * int(raw_deductions[1:])) / Decimal("100")
    tax = (gross * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    net = gross - tax - deductions
    if input_record[39:40] == "Y":
        net += Decimal("50.00")
    if net < 0:
        net = Decimal("0.00")
    if net >= Decimal("5000.00"):
        category = "H"
    elif net >= Decimal("2500.00"):
        category = "M"
    else:
        category = "L"
    cents = int((net * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return f"{emp_id}{emp_name[:12].ljust(12)}{cents:09d}{category}"
'''


CUSTOMER_SOLUTION = r'''
def migrate(input_record: str) -> str:
    cust_id = input_record[0:5]
    first = input_record[5:15].rstrip()
    last = input_record[15:27].rstrip()
    zip_code = input_record[27:32]
    status = {"A": "O", "S": "S"}.get(input_record[32:33], "C")
    balance = int(input_record[33:40])
    full_name = f"{last}, {first}"[:22].ljust(22)
    return f"{cust_id}{full_name}{zip_code}{status}{balance:08d}"
'''


CLAIMS_SOLUTION = r'''
def migrate(input_record: str) -> str:
    claim_id = input_record[0:6]
    age = int(input_record[6:9])
    plan = input_record[9:10]
    days = int(input_record[10:13])
    preauth = input_record[13:14]
    amount_cents = int(input_record[14:21])
    if age < 18:
        decision, reason = "D", "A1"
    elif plan == "B" and amount_cents > 150000:
        decision, reason = "R", "B2"
    elif preauth == "N" and amount_cents > 100000:
        decision, reason = "D", "P1"
    elif days > 30:
        decision, reason = "R", "L1"
    else:
        decision, reason = "A", "OK"
    return f"{claim_id}{decision}{reason}"
'''


ACCOUNT_SOLUTION = r'''
def migrate(input_record: str) -> str:
    account_id = input_record[0:6]
    status = input_record[6:7]
    raw_balance = input_record[7:16]
    sign = -1 if raw_balance[0] == "-" else 1
    balance_cents = sign * int(raw_balance[1:])
    days = int(input_record[16:19])
    if status == "C":
        category, action = "CL", "N"
    elif status == "F":
        category, action = "FR", "H"
    elif days >= 90:
        category, action = "DL", "C"
    elif balance_cents < 0:
        category, action = "OD", "R"
    else:
        category, action = "OK", "N"
    return f"{account_id}{category}{action}"
'''


INVOICE_SOLUTION = r'''
from decimal import Decimal, ROUND_HALF_UP


def migrate(input_record: str) -> str:
    invoice_id = input_record[0:6]
    count = min(int(input_record[6:8]), 4)
    tax_rates = {
        "S": Decimal("0.0725"),
        "R": Decimal("0.0250"),
        "L": Decimal("0.1000"),
    }
    total = Decimal("0.00")
    for idx in range(count):
        start = 8 + idx * 9
        qty = int(input_record[start:start + 2])
        price = Decimal(int(input_record[start + 2:start + 8])) / Decimal("100")
        tax_code = input_record[start + 8:start + 9]
        line = (Decimal(qty) * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax = (line * tax_rates.get(tax_code, Decimal("0.0000"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        line += tax
        total += line
    cents = int((total * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    flag = "H" if total >= Decimal("1000.00") else "L"
    return f"{invoice_id}{cents:09d}{count:02d}{flag}"
'''


DATE_SOLUTION = r'''
def is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def valid_date(year: int, month: int, day: int) -> bool:
    month_lengths = [31, 29 if is_leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return 1 <= month <= 12 and 1 <= day <= month_lengths[month - 1]


def migrate(input_record: str) -> str:
    policy_id = input_record[0:6]
    raw = input_record[6:12]
    window = int(input_record[12:14])
    amount = input_record[14:21]
    yy = int(raw[0:2])
    mm = int(raw[2:4])
    dd = int(raw[4:6])
    year = 1900 + yy if yy >= window else 2000 + yy
    normalized = f"{year:04d}{mm:02d}{dd:02d}" if valid_date(year, mm, dd) else "00000000"
    valid = "Y" if normalized != "00000000" else "N"
    return f"{policy_id}{normalized}{valid}{amount}"
'''


SOLUTIONS_BY_FAMILY = {
    "decimal_copybook_payroll": PAYROLL_SOLUTION,
    "fixed_width_customer": CUSTOMER_SOLUTION,
    "claims_eligibility_branching": CLAIMS_SOLUTION,
    "account_status_level88": ACCOUNT_SOLUTION,
    "invoice_occurs_totals": INVOICE_SOLUTION,
    "date_normalization": DATE_SOLUTION,
}


def solution_for_task(task: TaskInstance) -> str:
    try:
        return SOLUTIONS_BY_FAMILY[task.family_id].strip() + "\n"
    except KeyError as exc:
        raise ValueError(f"no oracle solution for family: {task.family_id}") from exc
