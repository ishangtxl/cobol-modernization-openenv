"""Task families for the Legacy COBOL Migration Workbench."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from random import Random
from typing import Any, Callable


@dataclass(frozen=True)
class TestCase:
    case_id: str
    input_record: str
    expected_output: str
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskInstance:
    task_id: str
    family_id: str
    domain: str
    ticket: str
    cobol_files: dict[str, str]
    copybooks: dict[str, str]
    expected_callable: str
    visible_tests: list[TestCase]
    hidden_tests: list[TestCase]
    metadata: dict[str, Any]


def cents(raw: str) -> Decimal:
    return Decimal(int(raw)) / Decimal("100")


def signed_cents(raw: str) -> Decimal:
    sign = -1 if raw[0] == "-" else 1
    return Decimal(sign * int(raw[1:])) / Decimal("100")


def money_cents(value: Decimal) -> int:
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def signed_field(value: int, width: int) -> str:
    sign = "-" if value < 0 else "+"
    return f"{sign}{abs(value):0{width - 1}d}"


def case_from(
    case_id: str,
    summary: str,
    record: str,
    reference: Callable[[str], str],
) -> TestCase:
    return TestCase(case_id, record, reference(record), summary)


def field(name: str, start: int, end: int, pic: str, python_type: str = "str", **extra: Any) -> dict[str, Any]:
    return {
        "name": name,
        "start": start,
        "end": end,
        "length": end - start,
        "pic": pic,
        "python_type": python_type,
        **extra,
    }


def copybook_layout_for(task: TaskInstance, filename: str) -> dict[str, Any]:
    copybook_layouts = task.metadata.get("copybook_layouts", {})
    if filename in copybook_layouts:
        return copybook_layouts[filename]
    return {
        "record_name": task.metadata["record_name"],
        "total_width": task.metadata["input_width"],
        "fields": task.metadata["copybook_layout"],
    }


def metadata(
    record_name: str,
    input_width: int,
    output_layout: list[dict[str, Any]],
    copybook_layout: list[dict[str, Any]],
    reference_rules: list[str],
    difficulty: str,
    fresh_seed: int,
    numeric_output_fields: list[str] | None = None,
    field_hints: dict[str, str] | None = None,
    agent_hints: list[str] | None = None,
    copybook_layouts: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    visible_hints = agent_hints or reference_rules
    return {
        "record_name": record_name,
        "input_width": input_width,
        "output_width": output_layout[-1]["end"],
        "output_layout": output_layout,
        "copybook_layout": copybook_layout,
        "difficulty": difficulty,
        "reference_rules": reference_rules,
        "agent_hints": visible_hints,
        "business_rules": visible_hints,
        "fresh_seed": fresh_seed,
        "numeric_output_fields": numeric_output_fields or [],
        "field_hints": field_hints or {},
        "copybook_layouts": copybook_layouts or {},
    }


# ---------------------------------------------------------------------------
# Family 1: Decimal payroll with copybook layout and level-88 bonus flag.
# ---------------------------------------------------------------------------

PAYROLL_LAYOUT = [
    field("EMP-ID", 0, 6, "X(6)"),
    field("EMP-NAME", 6, 18, "X(12)"),
    field("GROSS-PAY", 18, 27, "9(7)V99", "Decimal", scale=2),
    field("TAX-RATE", 27, 31, "9V999", "Decimal", scale=3),
    field("DEDUCTIONS", 31, 39, "S9(5)V99 SIGN LEADING SEPARATE", "Decimal", scale=2),
    field("BONUS-FLAG", 39, 40, "X(1)", level_88={"BONUS-ELIGIBLE": "Y", "NO-BONUS": "N"}),
    field("FILLER", 40, 42, "X(2)"),
]

PAYROLL_COPYBOOK = """       01  EMPLOYEE-PAY-RECORD.
           05 EMP-ID                 PIC X(6).
           05 EMP-NAME               PIC X(12).
           05 GROSS-PAY              PIC 9(7)V99.
           05 TAX-RATE               PIC 9V999.
           05 DEDUCTIONS             PIC S9(5)V99 SIGN LEADING SEPARATE.
           05 BONUS-FLAG             PIC X(1).
              88 BONUS-ELIGIBLE      VALUE 'Y'.
              88 NO-BONUS            VALUE 'N'.
           05 FILLER                 PIC X(2).
"""

PAYROLL_COBOL = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLLNET.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY EMPLOYEE_PAY.
       01 TAX-AMOUNT                 PIC 9(7)V99.
       01 NET-AMOUNT                 PIC 9(7)V99.
       01 PAY-CATEGORY               PIC X.
       PROCEDURE DIVISION.
           COMPUTE TAX-AMOUNT ROUNDED = GROSS-PAY * TAX-RATE
           COMPUTE NET-AMOUNT = GROSS-PAY - TAX-AMOUNT - DEDUCTIONS
           IF BONUS-ELIGIBLE ADD 50.00 TO NET-AMOUNT END-IF
           IF NET-AMOUNT < 0 MOVE 0 TO NET-AMOUNT END-IF
           EVALUATE TRUE
             WHEN NET-AMOUNT >= 5000.00 MOVE 'H' TO PAY-CATEGORY
             WHEN NET-AMOUNT >= 2500.00 MOVE 'M' TO PAY-CATEGORY
             WHEN OTHER MOVE 'L' TO PAY-CATEGORY
           END-EVALUATE
           GOBACK.
"""


def payroll_record(emp_id: str, name: str, gross: int, tax: int, deductions: int, bonus: str) -> str:
    return f"{emp_id[:6].ljust(6)}{name[:12].ljust(12)}{gross:09d}{tax:04d}{signed_field(deductions, 8)}{bonus}  "


def payroll_ref(record: str) -> str:
    emp_id = record[0:6]
    name = record[6:18]
    gross = cents(record[18:27])
    tax_rate = Decimal(int(record[27:31])) / Decimal("1000")
    deductions = signed_cents(record[31:39])
    tax = (gross * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    net = gross - tax - deductions
    if record[39:40] == "Y":
        net += Decimal("50.00")
    if net < 0:
        net = Decimal("0.00")
    category = "H" if net >= Decimal("5000.00") else "M" if net >= Decimal("2500.00") else "L"
    return f"{emp_id}{name[:12].ljust(12)}{money_cents(net):09d}{category}"


def payroll_task() -> TaskInstance:
    visible = [
        case_from("visible_1", "ordinary bonus-eligible employee", payroll_record("E00001", "ALICE", 123456, 185, 12345, "Y"), payroll_ref),
        case_from("visible_2", "negative adjustment and no bonus", payroll_record("E00002", "BOB", 82000, 125, -5000, "N"), payroll_ref),
        case_from("visible_3", "low net pay floors at zero", payroll_record("E00003", "CHANDRA", 20000, 315, 50000, "Y"), payroll_ref),
    ]
    hidden = [
        case_from("hidden_1", "high net category boundary", payroll_record("E00004", "DEEPA", 650000, 185, 25000, "N"), payroll_ref),
        case_from("hidden_2", "middle category with bonus", payroll_record("E00005", "EMIL", 310000, 75, 12500, "Y"), payroll_ref),
        case_from("hidden_3", "zero tax edge case", payroll_record("E00006", "FARAH", 255000, 0, 0, "N"), payroll_ref),
        case_from("hidden_4", "round half-up tax probe", payroll_record("E00007", "GITA", 100005, 185, 0, "N"), payroll_ref),
        case_from("hidden_5", "truncated long employee name", payroll_record("E00008", "HARIHARAN-RAO", 925000, 225, 100000, "Y"), payroll_ref),
    ]
    out = [
        field("OUT-EMP-ID", 0, 6, "X(6)"),
        field("OUT-EMP-NAME", 6, 18, "X(12)"),
        field("OUT-NET-PAY", 18, 27, "9(7)V99"),
        field("OUT-PAY-CATEGORY", 27, 28, "X"),
    ]
    return TaskInstance(
        "payroll_net_pay_001",
        "decimal_copybook_payroll",
        "payroll",
        "Migrate PAYROLL.cbl while preserving copybook offsets, implied decimals, signed deductions, bonus condition names, and fixed-width ACH output.",
        {"PAYROLL.cbl": PAYROLL_COBOL},
        {"EMPLOYEE_PAY.cpy": PAYROLL_COPYBOOK},
        "migrate(input_record: str) -> str",
        visible,
        hidden,
        metadata(
            "EMPLOYEE-PAY-RECORD",
            42,
            out,
            PAYROLL_LAYOUT,
            [
                "Tax is rounded half up to cents after GROSS-PAY * TAX-RATE.",
                "NET-AMOUNT = GROSS-PAY - TAX-AMOUNT - DEDUCTIONS.",
                "BONUS-ELIGIBLE adds 50.00; negative net pay floors to zero.",
                "Output net pay is a 9-digit zero-padded cents field.",
            ],
            "medium",
            20260425,
            ["OUT-NET-PAY"],
            {"OUT-NET-PAY": "zero-pad cents to 9 digits; do not emit a decimal point"},
        ),
    )


def payroll_fresh(seed: int, n: int) -> list[TestCase]:
    rng = Random(seed)
    return [
        case_from(
            f"fresh_{seed}_{i}",
            "fresh generated payroll edge case",
            payroll_record(f"F{i:05d}", f"Fresh{i}", rng.randint(75000, 925000), rng.choice([0, 75, 125, 185, 225, 315]), rng.randint(-25000, 180000), rng.choice(["Y", "N"])),
            payroll_ref,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Family 2: Fixed-width customer formatting.
# ---------------------------------------------------------------------------

CUSTOMER_LAYOUT = [
    field("CUST-ID", 0, 5, "X(5)"),
    field("FIRST-NAME", 5, 15, "X(10)"),
    field("LAST-NAME", 15, 27, "X(12)"),
    field("ZIP-CODE", 27, 32, "9(5)"),
    field("STATUS-CODE", 32, 33, "X"),
    field("BALANCE-DUE", 33, 40, "9(5)V99", "Decimal", scale=2),
]

CUSTOMER_COPYBOOK = """       01  CUSTOMER-RECORD.
           05 CUST-ID                PIC X(5).
           05 FIRST-NAME             PIC X(10).
           05 LAST-NAME              PIC X(12).
           05 ZIP-CODE               PIC 9(5).
           05 STATUS-CODE            PIC X.
              88 ACTIVE-CUSTOMER     VALUE 'A'.
              88 SUSPENDED-CUSTOMER  VALUE 'S'.
              88 CLOSED-CUSTOMER     VALUE 'C'.
           05 BALANCE-DUE            PIC 9(5)V99.
"""

CUSTOMER_COBOL = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CUSTFMT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY CUSTOMER_REC.
       01 OUTPUT-RECORD.
          05 OUT-CUST-ID             PIC X(5).
          05 OUT-FULL-NAME           PIC X(22).
          05 OUT-ZIP-CODE            PIC 9(5).
          05 OUT-STATUS              PIC X.
          05 OUT-BALANCE             PIC 9(6)V99.
       PROCEDURE DIVISION.
          STRING LAST-NAME DELIMITED BY SIZE ', ' FIRST-NAME DELIMITED BY SIZE
             INTO OUT-FULL-NAME
          EVALUATE STATUS-CODE
             WHEN 'A' MOVE 'O' TO OUT-STATUS
             WHEN 'S' MOVE 'S' TO OUT-STATUS
             WHEN OTHER MOVE 'C' TO OUT-STATUS
          END-EVALUATE
          GOBACK.
"""


def customer_record(cid: str, first: str, last: str, zip_code: int, status: str, balance: int) -> str:
    return f"{cid[:5].ljust(5)}{first[:10].ljust(10)}{last[:12].ljust(12)}{zip_code:05d}{status}{balance:07d}"


def customer_ref(record: str) -> str:
    cid = record[0:5]
    first = record[5:15].rstrip()
    last = record[15:27].rstrip()
    zip_code = record[27:32]
    status = {"A": "O", "S": "S"}.get(record[32:33], "C")
    balance = int(record[33:40])
    full_name = f"{last}, {first}"[:22].ljust(22)
    return f"{cid}{full_name}{zip_code}{status}{balance:08d}"


def customer_task() -> TaskInstance:
    visible = [
        case_from("visible_1", "active customer with short names", customer_record("C1001", "ALICE", "SHAH", 56001, "A", 12345), customer_ref),
        case_from("visible_2", "suspended customer with truncation", customer_record("C1002", "BENEDICT", "RAMANATHAN", 94105, "S", 5), customer_ref),
        case_from("visible_3", "closed customer mapping", customer_record("C1003", "CORA", "LEE", 10001, "C", 999999), customer_ref),
    ]
    hidden = [
        case_from("hidden_1", "unknown status maps closed", customer_record("C1004", "DEV", "NAIR", 70007, "X", 0), customer_ref),
        case_from("hidden_2", "long first and last names", customer_record("C1005", "ELIZABETH", "MUKHERJEE-RAO", 40001, "A", 100), customer_ref),
        case_from("hidden_3", "zip leading zero preserved", customer_record("C1006", "FINN", "ODELL", 501, "S", 54321), customer_ref),
    ]
    out = [
        field("OUT-CUST-ID", 0, 5, "X(5)"),
        field("OUT-FULL-NAME", 5, 27, "X(22)"),
        field("OUT-ZIP-CODE", 27, 32, "9(5)"),
        field("OUT-STATUS", 32, 33, "X"),
        field("OUT-BALANCE", 33, 41, "9(6)V99"),
    ]
    return TaskInstance(
        "customer_format_001",
        "fixed_width_customer",
        "customer master data",
        "Migrate CUSTFMT.cbl. Preserve fixed-width name formatting, status mapping, ZIP leading zeros, and zero-padded balance output.",
        {"CUSTFMT.cbl": CUSTOMER_COBOL},
        {"CUSTOMER_REC.cpy": CUSTOMER_COPYBOOK},
        "migrate(input_record: str) -> str",
        visible,
        hidden,
        metadata(
            "CUSTOMER-RECORD",
            40,
            out,
            CUSTOMER_LAYOUT,
            [
                "OUT-FULL-NAME is LAST-NAME, comma-space, FIRST-NAME, truncated/padded to 22.",
                "A maps to O, S maps to S, anything else maps to C.",
                "ZIP stays five digits and OUT-BALANCE is eight zero-padded digits.",
            ],
            "easy",
            20260426,
            ["OUT-ZIP-CODE", "OUT-BALANCE"],
            {"OUT-FULL-NAME": "format as LAST, FIRST within exactly 22 characters"},
        ),
    )


def customer_fresh(seed: int, n: int) -> list[TestCase]:
    rng = Random(seed)
    firsts = ["Mira", "Omar", "Priyanka", "Jun", "Leah", "Noah"]
    lasts = ["Iyer", "Fernandez", "Chakraborty", "Kim", "Banerjee", "Stone"]
    return [
        case_from(
            f"fresh_{seed}_{i}",
            "fresh customer formatting case",
            customer_record(f"F{i:04d}", rng.choice(firsts), rng.choice(lasts), rng.randint(1, 99999), rng.choice(["A", "S", "C", "X"]), rng.randint(0, 999999)),
            customer_ref,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Family 3: Claims eligibility branching.
# ---------------------------------------------------------------------------

CLAIMS_LAYOUT = [
    field("CLAIM-ID", 0, 6, "X(6)"),
    field("AGE", 6, 9, "9(3)", "int"),
    field("PLAN-CODE", 9, 10, "X"),
    field("SERVICE-DAYS", 10, 13, "9(3)", "int"),
    field("PREAUTH-FLAG", 13, 14, "X"),
    field("CLAIM-AMOUNT", 14, 21, "9(5)V99", "Decimal", scale=2),
]

CLAIMS_COPYBOOK = """       01  CLAIM-RECORD.
           05 CLAIM-ID               PIC X(6).
           05 AGE                    PIC 9(3).
           05 PLAN-CODE              PIC X.
           05 SERVICE-DAYS           PIC 9(3).
           05 PREAUTH-FLAG           PIC X.
           05 CLAIM-AMOUNT           PIC 9(5)V99.
"""

CLAIMS_COBOL = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. CLMELIG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY CLAIM_REC.
       PROCEDURE DIVISION.
          EVALUATE TRUE
             WHEN AGE < 18 MOVE 'D' TO DECISION MOVE 'A1' TO REASON
             WHEN PLAN-CODE = 'B' AND CLAIM-AMOUNT > 1500.00 MOVE 'R' TO DECISION MOVE 'B2' TO REASON
             WHEN PREAUTH-FLAG = 'N' AND CLAIM-AMOUNT > 1000.00 MOVE 'D' TO DECISION MOVE 'P1' TO REASON
             WHEN SERVICE-DAYS > 030 MOVE 'R' TO DECISION MOVE 'L1' TO REASON
             WHEN OTHER MOVE 'A' TO DECISION MOVE 'OK' TO REASON
          END-EVALUATE
          GOBACK.
"""


def claims_record(claim_id: str, age: int, plan: str, days: int, preauth: str, amount: int) -> str:
    return f"{claim_id[:6].ljust(6)}{age:03d}{plan}{days:03d}{preauth}{amount:07d}"


def claims_ref(record: str) -> str:
    claim_id = record[0:6]
    age = int(record[6:9])
    plan = record[9:10]
    days = int(record[10:13])
    preauth = record[13:14]
    amount = cents(record[14:21])
    if age < 18:
        decision, reason = "D", "A1"
    elif plan == "B" and amount > Decimal("1500.00"):
        decision, reason = "R", "B2"
    elif preauth == "N" and amount > Decimal("1000.00"):
        decision, reason = "D", "P1"
    elif days > 30:
        decision, reason = "R", "L1"
    else:
        decision, reason = "A", "OK"
    return f"{claim_id}{decision}{reason}"


def claims_task() -> TaskInstance:
    visible = [
        case_from("visible_1", "ordinary approved claim", claims_record("CLM001", 45, "A", 4, "Y", 80000), claims_ref),
        case_from("visible_2", "missing preauth denial", claims_record("CLM002", 52, "A", 5, "N", 125000), claims_ref),
        case_from("visible_3", "long service review", claims_record("CLM003", 33, "B", 45, "Y", 90000), claims_ref),
    ]
    hidden = [
        case_from("hidden_1", "minor denial takes precedence", claims_record("CLM004", 17, "B", 60, "N", 250000), claims_ref),
        case_from("hidden_2", "plan B large claim review precedes preauth", claims_record("CLM005", 30, "B", 10, "N", 175000), claims_ref),
        case_from("hidden_3", "boundary amount approved", claims_record("CLM006", 30, "A", 30, "N", 100000), claims_ref),
    ]
    out = [field("OUT-CLAIM-ID", 0, 6, "X(6)"), field("OUT-DECISION", 6, 7, "X"), field("OUT-REASON", 7, 9, "X(2)")]
    return TaskInstance(
        "claims_eligibility_001",
        "claims_eligibility_branching",
        "insurance claims",
        "Migrate CLMELIG.cbl. Preserve EVALUATE TRUE branch precedence for claim approvals, denials, and manual review reasons.",
        {"CLMELIG.cbl": CLAIMS_COBOL},
        {"CLAIM_REC.cpy": CLAIMS_COPYBOOK},
        "migrate(input_record: str) -> str",
        visible,
        hidden,
        metadata(
            "CLAIM-RECORD",
            21,
            out,
            CLAIMS_LAYOUT,
            [
                "Branch order matters: age, plan-B large claim, missing preauth, long service, default approve.",
                "Amounts are implied cents; 100000 means 1000.00.",
            ],
            "medium",
            20260427,
            [],
            {"OUT-REASON": "preserve the first matching branch reason code"},
        ),
    )


def claims_fresh(seed: int, n: int) -> list[TestCase]:
    rng = Random(seed)
    return [
        case_from(
            f"fresh_{seed}_{i}",
            "fresh claims branch case",
            claims_record(f"F{i:05d}", rng.randint(1, 90), rng.choice(["A", "B"]), rng.randint(1, 80), rng.choice(["Y", "N"]), rng.randint(25000, 250000)),
            claims_ref,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Family 4: Level-88 account status.
# ---------------------------------------------------------------------------

ACCOUNT_LAYOUT = [
    field("ACCOUNT-ID", 0, 6, "X(6)"),
    field("STATUS-CODE", 6, 7, "X", level_88={"ACTIVE-ACCT": "A", "FROZEN-ACCT": "F", "CLOSED-ACCT": "C"}),
    field("BALANCE", 7, 16, "S9(6)V99 SIGN LEADING SEPARATE", "Decimal", scale=2),
    field("DAYS-PAST-DUE", 16, 19, "9(3)", "int"),
]

ACCOUNT_COPYBOOK = """       01  ACCOUNT-RECORD.
           05 ACCOUNT-ID             PIC X(6).
           05 STATUS-CODE            PIC X.
              88 ACTIVE-ACCT         VALUE 'A'.
              88 FROZEN-ACCT         VALUE 'F'.
              88 CLOSED-ACCT         VALUE 'C'.
           05 BALANCE                PIC S9(6)V99 SIGN LEADING SEPARATE.
           05 DAYS-PAST-DUE          PIC 9(3).
"""

ACCOUNT_COBOL = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTSTAT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY ACCOUNT_REC.
       PROCEDURE DIVISION.
          EVALUATE TRUE
             WHEN CLOSED-ACCT MOVE 'CL' TO CATEGORY MOVE 'N' TO ACTION
             WHEN FROZEN-ACCT MOVE 'FR' TO CATEGORY MOVE 'H' TO ACTION
             WHEN DAYS-PAST-DUE >= 090 MOVE 'DL' TO CATEGORY MOVE 'C' TO ACTION
             WHEN BALANCE < 0 MOVE 'OD' TO CATEGORY MOVE 'R' TO ACTION
             WHEN OTHER MOVE 'OK' TO CATEGORY MOVE 'N' TO ACTION
          END-EVALUATE
          GOBACK.
"""


def account_record(account_id: str, status: str, balance: int, days: int) -> str:
    return f"{account_id[:6].ljust(6)}{status}{signed_field(balance, 9)}{days:03d}"


def account_ref(record: str) -> str:
    account_id = record[0:6]
    status = record[6:7]
    balance = signed_cents(record[7:16])
    days = int(record[16:19])
    if status == "C":
        category, action = "CL", "N"
    elif status == "F":
        category, action = "FR", "H"
    elif days >= 90:
        category, action = "DL", "C"
    elif balance < 0:
        category, action = "OD", "R"
    else:
        category, action = "OK", "N"
    return f"{account_id}{category}{action}"


def account_task() -> TaskInstance:
    visible = [
        case_from("visible_1", "active account in good standing", account_record("A00001", "A", 12345, 0), account_ref),
        case_from("visible_2", "overdrawn active account", account_record("A00002", "A", -1200, 10), account_ref),
        case_from("visible_3", "frozen account", account_record("A00003", "F", 999, 120), account_ref),
    ]
    hidden = [
        case_from("hidden_1", "closed overrides delinquency", account_record("A00004", "C", -500, 200), account_ref),
        case_from("hidden_2", "90 day delinquency boundary", account_record("A00005", "A", 0, 90), account_ref),
        case_from("hidden_3", "positive active account", account_record("A00006", "A", 10, 89), account_ref),
    ]
    out = [field("OUT-ACCOUNT-ID", 0, 6, "X(6)"), field("OUT-CATEGORY", 6, 8, "X(2)"), field("OUT-ACTION", 8, 9, "X")]
    return TaskInstance(
        "account_status_001",
        "account_status_level88",
        "banking",
        "Migrate ACCTSTAT.cbl. Correctly interpret level-88 status names and preserve branch precedence for account servicing actions.",
        {"ACCTSTAT.cbl": ACCOUNT_COBOL},
        {"ACCOUNT_REC.cpy": ACCOUNT_COPYBOOK},
        "migrate(input_record: str) -> str",
        visible,
        hidden,
        metadata(
            "ACCOUNT-RECORD",
            19,
            out,
            ACCOUNT_LAYOUT,
            [
                "CLOSED-ACCT and FROZEN-ACCT are level-88 names over STATUS-CODE.",
                "Closed and frozen branches precede delinquency and overdrawn checks.",
            ],
            "medium",
            20260428,
            [],
            {"OUT-CATEGORY": "do not treat level-88 names as separate variables"},
        ),
    )


def account_fresh(seed: int, n: int) -> list[TestCase]:
    rng = Random(seed)
    return [
        case_from(
            f"fresh_{seed}_{i}",
            "fresh account status case",
            account_record(f"F{i:05d}", rng.choice(["A", "F", "C"]), rng.randint(-25000, 100000), rng.randint(0, 180)),
            account_ref,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Family 5: OCCURS invoice table processing.
# ---------------------------------------------------------------------------

INVOICE_LINE_ITEM_LAYOUT = [
    field("ITEM-QTY", 0, 2, "9(2)", "int"),
    field("ITEM-PRICE", 2, 8, "9(4)V99", "Decimal", scale=2),
    field("TAX-CODE", 8, 9, "X"),
]

INVOICE_LAYOUT = [
    field("INVOICE-ID", 0, 6, "X(6)"),
    field("ITEM-COUNT", 6, 8, "9(2)", "int"),
    field("LINE-ITEMS", 8, 44, "OCCURS 4 TIMES", "group", occurs=4, stride=9, children=INVOICE_LINE_ITEM_LAYOUT),
]

TAX_CODE_ENTRY_LAYOUT = [
    field("TAX-CODE-KEY", 0, 1, "X"),
    field("TAX-RATE", 1, 5, "9V9999", "Decimal", scale=4),
]

TAX_CODE_LAYOUT = [
    field("TAX-CODE-ENTRIES", 0, 20, "OCCURS 4 TIMES", "group", occurs=4, stride=5, children=TAX_CODE_ENTRY_LAYOUT),
]

INVOICE_COPYBOOK = """       01  INVOICE-RECORD.
           05 INVOICE-ID             PIC X(6).
           05 ITEM-COUNT             PIC 9(2).
           05 LINE-ITEM OCCURS 4 TIMES.
              10 ITEM-QTY            PIC 9(2).
              10 ITEM-PRICE          PIC 9(4)V99.
              10 TAX-CODE            PIC X.
"""

TAX_CODE_COPYBOOK = """       01  TAX-CODE-TABLE.
           05 TAX-CODE-ENTRY OCCURS 4 TIMES.
              10 TAX-CODE-KEY        PIC X.
              10 TAX-RATE            PIC 9V9999.
"""

INVOICE_COBOL = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. INVTOTAL.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY INVOICE_REC.
       COPY TAX_CODE.
       01 IDX                        PIC 9 VALUE 0.
       01 LINE-AMOUNT                PIC 9(7)V99 VALUE 0.
       01 TAX-AMOUNT                 PIC 9(7)V99 VALUE 0.
       01 TAX-PERCENT                PIC 9V9999 VALUE 0.
       01 INVOICE-TOTAL              PIC 9(7)V99 VALUE 0.
       PROCEDURE DIVISION.
          PERFORM VARYING IDX FROM 1 BY 1 UNTIL IDX > ITEM-COUNT
             COMPUTE LINE-AMOUNT ROUNDED = ITEM-QTY(IDX) * ITEM-PRICE(IDX)
             CALL 'TAXRATE' USING TAX-CODE(IDX) TAX-PERCENT
             COMPUTE TAX-AMOUNT ROUNDED = LINE-AMOUNT * TAX-PERCENT
             ADD TAX-AMOUNT TO LINE-AMOUNT
             ADD LINE-AMOUNT TO INVOICE-TOTAL
          END-PERFORM
          GOBACK.
"""

TAXRATE_COBOL = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. TAXRATE.
       DATA DIVISION.
       LINKAGE SECTION.
       01 LK-TAX-CODE                PIC X.
       01 LK-TAX-PERCENT             PIC 9V9999.
       PROCEDURE DIVISION USING LK-TAX-CODE LK-TAX-PERCENT.
          EVALUATE LK-TAX-CODE
             WHEN 'S' MOVE 0.0725 TO LK-TAX-PERCENT
             WHEN 'R' MOVE 0.0250 TO LK-TAX-PERCENT
             WHEN 'L' MOVE 0.1000 TO LK-TAX-PERCENT
             WHEN OTHER MOVE 0.0000 TO LK-TAX-PERCENT
          END-EVALUATE
          GOBACK.
"""

INVOICE_TAX_RATES = {
    "S": Decimal("0.0725"),
    "R": Decimal("0.0250"),
    "L": Decimal("0.1000"),
}


def invoice_record(invoice_id: str, items: list[tuple[int, int, str]]) -> str:
    padded = items[:4] + [(0, 0, "N")] * (4 - len(items[:4]))
    groups = "".join(f"{qty:02d}{price:06d}{tax_code}" for qty, price, tax_code in padded)
    return f"{invoice_id[:6].ljust(6)}{len(items[:4]):02d}{groups}"


def invoice_ref(record: str) -> str:
    invoice_id = record[0:6]
    count = min(int(record[6:8]), 4)
    total = Decimal("0.00")
    for idx in range(count):
        start = 8 + idx * 9
        qty = int(record[start : start + 2])
        price = cents(record[start + 2 : start + 8])
        tax_code = record[start + 8 : start + 9]
        line = (Decimal(qty) * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax = (line * INVOICE_TAX_RATES.get(tax_code, Decimal("0.0000"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        line += tax
        total += line
    flag = "H" if total >= Decimal("1000.00") else "L"
    return f"{invoice_id}{money_cents(total):09d}{count:02d}{flag}"


def invoice_task() -> TaskInstance:
    visible = [
        case_from("visible_1", "two standard and non-taxable lines", invoice_record("I00001", [(2, 12345, "S"), (1, 10000, "N")]), invoice_ref),
        case_from("visible_2", "zero item invoice", invoice_record("I00002", []), invoice_ref),
        case_from("visible_3", "four item high invoice", invoice_record("I00003", [(4, 25000, "S"), (1, 99000, "N"), (3, 12345, "R"), (2, 50000, "L")]), invoice_ref),
    ]
    hidden = [
        case_from("hidden_1", "standard tax rounding probe", invoice_record("I00004", [(3, 33333, "S")]), invoice_ref),
        case_from("hidden_2", "count ignores padded groups", invoice_record("I00005", [(1, 100, "N")]), invoice_ref),
        case_from("hidden_3", "threshold flag high with luxury code", invoice_record("I00006", [(4, 30000, "L")]), invoice_ref),
        case_from("hidden_4", "reduced code generalization", invoice_record("I00007", [(7, 22222, "R"), (2, 10101, "S")]), invoice_ref),
    ]
    out = [
        field("OUT-INVOICE-ID", 0, 6, "X(6)"),
        field("OUT-TOTAL", 6, 15, "9(7)V99"),
        field("OUT-ITEM-COUNT", 15, 17, "9(2)"),
        field("OUT-FLAG", 17, 18, "X"),
    ]
    return TaskInstance(
        "invoice_occurs_001",
        "invoice_occurs_totals",
        "invoicing",
        "Migrate INVTOTAL.cbl and TAXRATE.cbl. Preserve OCCURS stride parsing, item-count bounds, tax-code lookup behavior, and fixed-width total output.",
        {"INVTOTAL.cbl": INVOICE_COBOL, "TAXRATE.cbl": TAXRATE_COBOL},
        {"INVOICE_REC.cpy": INVOICE_COPYBOOK, "TAX_CODE.cpy": TAX_CODE_COPYBOOK},
        "migrate(input_record: str) -> str",
        visible,
        hidden,
        metadata(
            "INVOICE-RECORD",
            44,
            out,
            INVOICE_LAYOUT,
            [
                "LINE-ITEM OCCURS 4 TIMES with a 9-byte stride.",
                "Only the first ITEM-COUNT entries contribute to the total.",
                "Each line's TAX-CODE maps through TAXRATE: S=0.0725, R=0.0250, L=0.1000, and other codes are zero-rated.",
                "Tax is rounded half up per line from LINE-AMOUNT * TAX-PERCENT, then added to the line before totaling.",
            ],
            "hard",
            20260429,
            ["OUT-TOTAL", "OUT-ITEM-COUNT"],
            {"OUT-TOTAL": "sum line totals as cents and zero-pad to 9 digits"},
            [
                "LINE-ITEM OCCURS 4 TIMES with a 9-byte stride.",
                "Only the first ITEM-COUNT entries contribute to the total.",
                "Tax codes are resolved through the separate TAXRATE program; handle all code branches found there.",
                "Keep the total, item count, and high/low flag in the fixed-width output layout.",
            ],
            {
                "INVOICE_REC.cpy": {
                    "record_name": "INVOICE-RECORD",
                    "total_width": 44,
                    "fields": INVOICE_LAYOUT,
                },
                "TAX_CODE.cpy": {
                    "record_name": "TAX-CODE-TABLE",
                    "total_width": 20,
                    "fields": TAX_CODE_LAYOUT,
                },
            },
        ),
    )


def invoice_fresh(seed: int, n: int) -> list[TestCase]:
    rng = Random(seed)
    cases = []
    for i in range(n):
        item_count = rng.randint(0, 4)
        items = [(rng.randint(1, 9), rng.randint(100, 99999), rng.choice(["S", "R", "L", "N", "X"])) for _ in range(item_count)]
        cases.append(case_from(f"fresh_{seed}_{i}", "fresh invoice occurs case", invoice_record(f"F{i:05d}", items), invoice_ref))
    return cases


# ---------------------------------------------------------------------------
# Family 6: Legacy date normalization.
# ---------------------------------------------------------------------------

DATE_LAYOUT = [
    field("POLICY-ID", 0, 6, "X(6)"),
    field("RAW-DATE", 6, 12, "9(6)", "str"),
    field("WINDOW-YEAR", 12, 14, "9(2)", "int"),
    field("AMOUNT", 14, 21, "9(5)V99", "Decimal", scale=2),
]

DATE_COPYBOOK = """       01  POLICY-DATE-RECORD.
           05 POLICY-ID              PIC X(6).
           05 RAW-DATE               PIC 9(6).
           05 WINDOW-YEAR            PIC 9(2).
           05 AMOUNT                 PIC 9(5)V99.
"""

DATE_COBOL = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. DATENORM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY POLICY_DATE.
       PROCEDURE DIVISION.
          IF RAW-YY >= WINDOW-YEAR
             MOVE 19 TO OUT-CENTURY
          ELSE
             MOVE 20 TO OUT-CENTURY
          END-IF
          PERFORM VALIDATE-MONTH-DAY
          GOBACK.
"""


def date_record(policy_id: str, raw_yymmdd: str, window: int, amount: int) -> str:
    return f"{policy_id[:6].ljust(6)}{raw_yymmdd}{window:02d}{amount:07d}"


def is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def valid_date(year: int, month: int, day: int) -> bool:
    month_lengths = [31, 29 if is_leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return 1 <= month <= 12 and 1 <= day <= month_lengths[month - 1]


def date_ref(record: str) -> str:
    policy_id = record[0:6]
    raw = record[6:12]
    window = int(record[12:14])
    amount = record[14:21]
    yy = int(raw[0:2])
    mm = int(raw[2:4])
    dd = int(raw[4:6])
    year = 1900 + yy if yy >= window else 2000 + yy
    normalized = f"{year:04d}{mm:02d}{dd:02d}" if valid_date(year, mm, dd) else "00000000"
    valid = "Y" if normalized != "00000000" else "N"
    return f"{policy_id}{normalized}{valid}{amount}"


def date_task() -> TaskInstance:
    visible = [
        case_from("visible_1", "twentieth century date by window", date_record("P00001", "991231", 50, 12345), date_ref),
        case_from("visible_2", "twenty-first century date by window", date_record("P00002", "240229", 50, 100), date_ref),
        case_from("visible_3", "invalid month", date_record("P00003", "241331", 50, 999), date_ref),
    ]
    hidden = [
        case_from("hidden_1", "non-leap invalid February", date_record("P00004", "230229", 50, 1000), date_ref),
        case_from("hidden_2", "window boundary goes 19xx", date_record("P00005", "500101", 50, 4321), date_ref),
        case_from("hidden_3", "valid leap day 2000", date_record("P00006", "000229", 50, 555), date_ref),
    ]
    out = [
        field("OUT-POLICY-ID", 0, 6, "X(6)"),
        field("OUT-DATE", 6, 14, "9(8)"),
        field("OUT-VALID", 14, 15, "X"),
        field("OUT-AMOUNT", 15, 22, "9(5)V99"),
    ]
    return TaskInstance(
        "date_normalization_001",
        "date_normalization",
        "claims and billing",
        "Migrate DATENORM.cbl. Preserve legacy YYMMDD century-window rules and invalid-date behavior instead of blindly using modern date parsing.",
        {"DATENORM.cbl": DATE_COBOL},
        {"POLICY_DATE.cpy": DATE_COPYBOOK},
        "migrate(input_record: str) -> str",
        visible,
        hidden,
        metadata(
            "POLICY-DATE-RECORD",
            21,
            out,
            DATE_LAYOUT,
            [
                "RAW-DATE is YYMMDD.",
                "If YY >= WINDOW-YEAR, century is 19; otherwise century is 20.",
                "Invalid dates output 00000000 and valid flag N; amount is preserved.",
            ],
            "medium",
            20260430,
            ["OUT-DATE", "OUT-AMOUNT"],
            {"OUT-DATE": "apply the two-digit century window before validating month/day"},
        ),
    )


def date_fresh(seed: int, n: int) -> list[TestCase]:
    rng = Random(seed)
    cases = []
    for i in range(n):
        yy = rng.randint(0, 99)
        mm = rng.randint(1, 14)
        dd = rng.randint(1, 32)
        cases.append(
            case_from(
                f"fresh_{seed}_{i}",
                "fresh date normalization case",
                date_record(f"F{i:05d}", f"{yy:02d}{mm:02d}{dd:02d}", rng.choice([40, 50, 70]), rng.randint(0, 999999)),
                date_ref,
            )
        )
    return cases


TASK_BUILDERS: list[Callable[[], TaskInstance]] = [
    payroll_task,
    customer_task,
    claims_task,
    account_task,
    invoice_task,
    date_task,
]

FRESH_GENERATORS: dict[str, Callable[[int, int], list[TestCase]]] = {
    "decimal_copybook_payroll": payroll_fresh,
    "fixed_width_customer": customer_fresh,
    "claims_eligibility_branching": claims_fresh,
    "account_status_level88": account_fresh,
    "invoice_occurs_totals": invoice_fresh,
    "date_normalization": date_fresh,
}


def all_tasks() -> list[TaskInstance]:
    return [builder() for builder in TASK_BUILDERS]


def load_task(seed: int | None = None, task_id: str | None = None) -> TaskInstance:
    tasks = all_tasks()
    if task_id is not None:
        for task in tasks:
            if task.task_id == task_id or task.family_id == task_id:
                return task
        raise ValueError(f"unknown task_id: {task_id}")
    if seed is None:
        return tasks[0]
    return tasks[seed % len(tasks)]


def generate_fresh_tests(task: TaskInstance, seed: int | None = None, n: int = 6) -> list[TestCase]:
    generator = FRESH_GENERATORS[task.family_id]
    return generator(seed if seed is not None else task.metadata["fresh_seed"], n)
