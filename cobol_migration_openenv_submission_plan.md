# Legacy COBOL Migration Workbench
## Standalone OpenEnv Hackathon Plan

This document is a complete, standalone plan for building and submitting an OpenEnv environment for the OpenEnv Hackathon India 2026.

The project is a professional world-modeling environment where an LLM acts inside a legacy modernization workbench. The agent must inspect COBOL programs, copybooks, record layouts, tests, and execution feedback, then produce Python code that preserves the business behavior of the original system.

The target submission theme is:

- Primary: Theme #3.1, World Modeling - Professional Tasks
- Secondary: Theme #2, Long-Horizon Planning and Instruction Following

The core idea is not "translate COBOL into Python from a prompt." The core idea is:

> Train an LLM to behave like a legacy modernization engineer inside a partially observable migration workbench.

The environment should teach and evaluate tool use, state tracking, debugging, semantic preservation, copybook reasoning, and safe code execution.

---

## 1. Executive Summary

### 1.1 Project Name

Legacy COBOL Migration Workbench

### 1.2 One-Sentence Pitch

An OpenEnv environment where an LLM learns to inspect legacy COBOL systems, use migration tools, debug failed tests, and produce semantically equivalent Python under hidden and fresh verification.

### 1.3 Problem Statement

Many critical financial, insurance, government, payroll, and logistics systems still encode business logic in COBOL. Migrating these systems is difficult because correctness depends on fixed-width records, copybooks, decimal arithmetic, field layouts, legacy control flow, and subtle business edge cases.

A realistic migration assistant cannot simply translate code in one shot. It must:

- inspect multiple files,
- understand copybook layouts,
- infer field boundaries,
- preserve decimal and fixed-width behavior,
- run tests,
- interpret failures,
- revise its solution,
- and avoid unsafe or hardcoded shortcuts.

This project builds an RL environment where an LLM practices that workflow and receives verifiable rewards.

### 1.4 What The Agent Learns

The agent should improve at:

- using tools in the right order,
- reading only partial information and deciding what to inspect next,
- maintaining state across a multi-step migration episode,
- converting COBOL semantics into Python,
- debugging based on visible test failures,
- preserving business behavior on hidden and fresh tests,
- avoiding hardcoding visible examples,
- producing safe, importable, executable Python.

### 1.5 Why This Fits The Hackathon

This environment matches the judging criteria directly:

- Environment Innovation: COBOL modernization is underexplored and professionally meaningful.
- Storytelling: the demo can be framed as "retiring a fragile mainframe workflow safely."
- Reward Improvement: correctness is objectively measurable through tests.
- Training Pipeline: OpenEnv plus TRL or Unsloth can train against the live environment.

### 1.6 What A Strong Demo Shows

The demo should show one baseline-vs-trained episode:

1. A migration ticket asks the agent to migrate a payroll, invoice, claims, or ledger COBOL program.
2. The baseline model submits code too early or ignores the copybook.
3. Visible tests fail because of decimal, fixed-width, or layout mistakes.
4. The trained model reads the copybook, parses field offsets, runs visible tests, inspects diffs, revises code, and submits.
5. Hidden and fresh tests show measurable improvement.

---

## 2. Submission Goals

### 2.1 Minimum Valid Submission

The minimum submission must include:

- an OpenEnv-compliant environment,
- a hosted Hugging Face Space,
- a valid `openenv.yaml`,
- standard `reset`, `step`, and `state` behavior,
- a small but working task bank,
- composable reward functions,
- a minimal TRL or Unsloth training script,
- evidence of at least one real training run,
- reward/loss plots,
- baseline-vs-trained examples,
- a README that links all artifacts,
- a short video, blog post, or slide deck.

### 2.2 Strong Submission

A strong submission should include:

- 8 to 12 validated task families,
- 100 to 300 compiled task instances,
- hidden and fresh test evaluation,
- family-held-out and parameter-held-out splits,
- visible improvement after training,
- a clear story around legacy modernization,
- a polished Space demo,
- a short video under 2 minutes,
- readable plots committed to the repository.

### 2.3 Stretch Submission

Stretch goals:

- 12 to 18 task families,
- 300+ task instances,
- multiple base model comparisons,
- process-reward ablation,
- copybook-heavy success case,
- realistic multi-file mini-app migration tasks,
- self-generated curriculum for harder migration tasks.

---

## 3. Theme Alignment

### 3.1 Primary Theme: World Modeling / Professional Tasks

This environment captures a partially observable professional world:

- the agent does not receive all useful information up front,
- source files and copybooks must be inspected through tools,
- visible tests reveal only partial behavior,
- hidden tests verify generalization,
- tool outputs update the agent's belief about the system,
- the agent must coordinate a multi-step workflow.

The environment is not a static benchmark. It is an interaction loop.

### 3.2 Secondary Theme: Long-Horizon Planning

Longer tasks can require:

- reading multiple source files,
- reading multiple copybooks,
- understanding field layouts,
- producing a first Python draft,
- running tests,
- diagnosing failures,
- revising code,
- submitting final code,
- preserving decisions across many turns.

The horizon can be increased by adding multi-file programs, more hidden edge cases, and tasks where early mistakes propagate into later failures.

### 3.3 Why Not Multi-Agent By Default

The core idea does not need multi-agent interaction. Adding simulated reviewers, QA agents, or business stakeholders is possible later, but it should not be part of the first submission unless the environment is already stable.

### 3.4 Why Not Self-Improvement By Default

Self-improvement can be added later through adaptive task generation or self-play task creation, but the primary contribution should be a reliable professional migration environment.

---

## 4. Scope And COBOL Subset

The environment must define exactly which COBOL semantics it supports. This is necessary for scientific validity and for fair rewards.

### 4.1 Chosen COBOL Style

Use a documented, constrained batch-processing subset of COBOL.

The recommended authoring oracle is:

- one fixed COBOL dialect/compiler for validation,
- one documented runtime configuration,
- one set of numeric and string rules,
- one deterministic test harness.

If a compiler-backed oracle is available, use it during task authoring and parity validation. If not, every supported construct must have manually reviewed reference semantics.

### 4.2 Supported Program Shape

Initial programs should look like small enterprise batch logic:

- input record or structured input,
- working-storage variables,
- procedure division logic,
- output record or structured output,
- no interactive terminal input,
- no network,
- no real database,
- no external system calls.

### 4.3 Supported COBOL Constructs

Core constructs:

- `IDENTIFICATION DIVISION`
- `DATA DIVISION`
- `WORKING-STORAGE SECTION`
- simple `LINKAGE SECTION` style interfaces if useful
- `PROCEDURE DIVISION`
- `MOVE`
- `COMPUTE`
- `ADD`
- `SUBTRACT`
- `MULTIPLY`
- `DIVIDE`
- `IF` / `ELSE` / `END-IF`
- `EVALUATE` / `WHEN`
- `PERFORM`
- `PERFORM VARYING`
- simple paragraphs and sections
- `INSPECT TALLYING`
- `INSPECT REPLACING`
- `STRING` and `UNSTRING` only if semantics are tightly specified

Data and layout constructs:

- `PIC X(n)`
- `PIC 9(n)`
- signed decimal fields
- implied decimals such as `V99`
- simple edited output if explicitly specified
- level-01 records
- level-05 and level-10 fields
- copybooks
- level-88 condition names
- simple `OCCURS`
- limited `REDEFINES` only after the basic environment is stable.

### 4.4 Supported Python Output

The model should submit Python code that exposes a required callable, for example:

```python
def migrate(input_record: str) -> str:
    ...
```

or:

```python
def migrate(payload: dict) -> dict:
    ...
```

The interface can vary by task family, but every compiled task must specify:

- expected function name,
- input schema,
- output schema,
- allowed imports,
- timeout,
- memory limit,
- visible tests,
- hidden tests,
- fresh test generator.

### 4.5 Explicit Non-Goals

The first version should not attempt:

- full COBOL language coverage,
- CICS,
- DB2,
- JCL execution,
- VSAM behavior,
- indexed files,
- real mainframe emulation,
- unrestricted `REDEFINES`,
- arbitrary `COPY REPLACING`,
- packed decimal byte-level compatibility unless tested carefully,
- migration of very large codebases in a single episode.

These can be future extensions.

---

## 5. Environment Design

### 5.1 OpenEnv Compliance

The environment must use OpenEnv properly.

Required behavior:

- `reset()` starts a new episode and returns the initial observation.
- `step(action)` applies one agent action and returns observation, reward, done flag, and metadata.
- `state()` returns the current environment state for inspection.
- The client must not import server internals.
- The environment must provide a valid `openenv.yaml`.
- The environment must avoid reserved tool names such as `reset`, `step`, `state`, and `close`.
- The environment must be runnable locally and hosted on Hugging Face Spaces.

### 5.2 Episode Concept

Each episode is one migration ticket.

The ticket contains:

- business context,
- target behavior,
- available source files,
- available copybooks,
- expected Python interface,
- visible test budget,
- max step limit.

The agent starts with only partial information. It can inspect files and run tools to uncover more.

### 5.3 Observation Design

Initial observation should include:

- ticket ID,
- business domain,
- high-level migration request,
- list of available artifacts,
- expected output interface,
- current step count,
- allowed actions,
- previous tool result if any.

It should not include:

- hidden tests,
- reference Python implementation,
- full copybook parse unless the agent calls a tool,
- final answer,
- direct reward internals that enable hacking.

Example initial observation:

```json
{
  "ticket_id": "payroll_tax_042",
  "domain": "payroll",
  "request": "Migrate the COBOL payroll tax calculation into Python.",
  "available_files": ["PAYTAX.cbl", "EMPLOYEE.cpy"],
  "expected_callable": "migrate(input_record: str) -> str",
  "visible_tests_available": true,
  "max_steps": 12,
  "step": 0
}
```

### 5.4 Action Design

Actions should be typed and constrained.

Recommended action types:

- `read_cobol_file`
- `read_copybook`
- `parse_copybook_layout`
- `inspect_business_rules`
- `write_python_solution`
- `run_visible_tests`
- `inspect_diff`
- `submit_final`

Do not make the model call arbitrary shell commands.

### 5.5 Tool API

#### `read_cobol_file`

Purpose:

- reveal COBOL source code.

Input:

```json
{"filename": "PAYTAX.cbl"}
```

Output:

```json
{
  "filename": "PAYTAX.cbl",
  "content": "...",
  "truncated": false
}
```

#### `read_copybook`

Purpose:

- reveal raw copybook content.

Input:

```json
{"filename": "EMPLOYEE.cpy"}
```

Output:

```json
{
  "filename": "EMPLOYEE.cpy",
  "content": "..."
}
```

#### `parse_copybook_layout`

Purpose:

- provide structured field offsets, lengths, types, implied decimals, and level-88 conditions.

Input:

```json
{"filename": "EMPLOYEE.cpy"}
```

Output:

```json
{
  "record_name": "EMPLOYEE-RECORD",
  "total_width": 64,
  "fields": [
    {
      "name": "EMP-ID",
      "start": 0,
      "end": 8,
      "length": 8,
      "pic": "X(8)",
      "python_type": "str"
    },
    {
      "name": "GROSS-PAY",
      "start": 8,
      "end": 17,
      "length": 9,
      "pic": "9(7)V99",
      "python_type": "Decimal",
      "scale": 2
    }
  ]
}
```

This tool makes the environment more realistic and less dependent on the model memorizing COBOL field-layout rules.

#### `inspect_business_rules`

Purpose:

- summarize named branches, level-88 conditions, thresholds, and output conditions from metadata generated during authoring.

This tool should not reveal hidden expected outputs. It should reveal structural information a migration engineer could infer from source inspection.

#### `write_python_solution`

Purpose:

- store a draft Python solution in the environment.

Input:

```json
{
  "code": "from decimal import Decimal\n\ndef migrate(input_record: str) -> str:\n    ..."
}
```

Output:

```json
{
  "stored": true,
  "syntax_ok": true,
  "interface_ok": true,
  "draft_id": 2
}
```

#### `run_visible_tests`

Purpose:

- execute the current draft against visible tests.

Input:

```json
{"draft_id": 2}
```

Output:

```json
{
  "passed": 3,
  "total": 5,
  "failures": [
    {
      "case_id": "visible_3",
      "input_summary": "negative adjustment with tax code B",
      "expected_summary": "fixed-width amount differs",
      "actual_summary": "amount has wrong decimal scale"
    }
  ]
}
```

Visible tests should provide useful debugging signal without revealing the full hidden mapping.

#### `inspect_diff`

Purpose:

- show structured differences for failed visible tests.

Input:

```json
{"case_id": "visible_3"}
```

Output:

```json
{
  "case_id": "visible_3",
  "field_diffs": [
    {
      "field": "NET-PAY",
      "expected": "00012345",
      "actual": "123.45",
      "hint": "output must be fixed-width cents with zero padding"
    }
  ]
}
```

The diff should be useful but not so rich that the model can reverse-engineer the full solution from examples alone.

#### `submit_final`

Purpose:

- submit the final Python solution for hidden and fresh evaluation.

Input:

```json
{"draft_id": 2}
```

Output:

```json
{
  "accepted": true,
  "episode_done": true,
  "public_score": 0.78
}
```

Do not reveal hidden test details in the normal agent observation.

### 5.6 State Representation

The internal state should track:

- selected task instance,
- current step count,
- files read,
- copybooks read,
- parsed layouts requested,
- drafts submitted,
- syntax/interface results,
- visible test runs,
- visible failures inspected,
- best visible pass rate so far,
- final submission status,
- sandbox execution metadata,
- reward component values.

### 5.7 Termination Conditions

An episode ends when:

- `submit_final` is called,
- max steps are reached,
- repeated invalid actions exceed a threshold,
- unsafe code is detected,
- execution repeatedly times out,
- environment error occurs.

### 5.8 Partial Observability

The agent should not see everything by default. It must decide which artifacts to inspect.

Partial observability is important because it forces world modeling:

- if a copybook exists but is not read, the model may misunderstand field boundaries,
- if tests fail but diffs are not inspected, the model has less feedback,
- if the model submits early, it risks hidden failures.

---

## 6. Task Family System

### 6.1 Why Task Families

Do not hand-author hundreds of disconnected tasks.

Instead, define task families that generate many parameterized instances. Each family represents one semantic challenge and can produce:

- COBOL source,
- copybook files,
- business ticket text,
- Python reference implementation,
- input generators,
- visible tests,
- hidden tests,
- fresh tests,
- reward metadata.

This enables scale, reproducibility, and controlled splits.

### 6.2 Family Interface

Recommended Python interface:

```python
from dataclasses import dataclass
from typing import Callable, Literal

Split = Literal["train", "val", "test", "fresh"]

@dataclass
class TestCase:
    case_id: str
    input_payload: object
    expected_output: object
    metadata: dict

@dataclass
class TaskInstance:
    task_id: str
    family_id: str
    tier: int
    domain: str
    ticket: str
    cobol_files: dict[str, str]
    copybooks: dict[str, str]
    expected_callable: str
    input_schema: dict
    output_schema: dict
    visible_tests: list[TestCase]
    hidden_tests: list[TestCase]
    metadata: dict

class TaskFamily:
    family_id: str
    tier: int
    domain: str
    required_tools: list[str]
    supported_constructs: list[str]
    failure_modes: list[str]

    def render_instance(self, seed: int, split: Split) -> TaskInstance:
        ...

    def reference_implementation(self) -> Callable:
        ...

    def generate_tests(self, seed: int, split: Split, n: int) -> list[TestCase]:
        ...
```

### 6.3 Required Family Artifacts

Each family must provide:

- `family_id`,
- tier,
- business domain,
- semantic construct,
- one or more COBOL templates,
- optional copybook templates,
- input generator,
- reference implementation,
- visible test sampler,
- hidden test sampler,
- fresh test sampler,
- type-fidelity checks,
- hardcoding checks,
- required tool metadata,
- common failure modes,
- human-review notes.

### 6.4 Recommended Task Families

#### Family 1: Decimal Payroll Calculation

Domain:

- payroll

COBOL concepts:

- signed decimal arithmetic,
- implied decimals,
- rounding,
- `COMPUTE`,
- `IF`.

Migration challenge:

- Python must use `Decimal` or equivalent exact decimal behavior.
- Float solutions should fail precision probes.

Example business story:

- compute net pay from gross pay, tax rate, deductions, and adjustment flags.

Failure modes:

- binary float drift,
- wrong rounding,
- sign handling,
- missing zero padding.

#### Family 2: Fixed-Width Customer Record Formatting

Domain:

- customer master data

COBOL concepts:

- `PIC X(n)`,
- `PIC 9(n)`,
- `MOVE`,
- string padding and truncation.

Migration challenge:

- output must preserve exact field widths.

Failure modes:

- trimming spaces,
- failing to truncate,
- wrong right/left alignment,
- wrong zero padding.

#### Family 3: Invoice Total With Running Accumulator

Domain:

- invoicing

COBOL concepts:

- `PERFORM VARYING`,
- accumulators,
- decimal arithmetic,
- final formatting.

Migration challenge:

- compute totals over line items with taxes, discounts, and thresholds.

Failure modes:

- off-by-one loop,
- wrong accumulator initialization,
- wrong rounding stage,
- hardcoded visible totals.

#### Family 4: Claims Eligibility Branching

Domain:

- insurance claims

COBOL concepts:

- nested `IF`,
- `EVALUATE TRUE`,
- level-88 style conditions.

Migration challenge:

- preserve branch precedence and edge cases.

Failure modes:

- wrong branch order,
- missing default case,
- boundary mistakes.

#### Family 5: Account Status Using Level-88 Conditions

Domain:

- banking

COBOL concepts:

- level-88 condition names,
- status codes,
- conditional business logic.

Migration challenge:

- recognize symbolic condition names and map them to underlying field values.

Failure modes:

- ignoring level-88 definitions,
- treating condition names as variables,
- wrong status category.

#### Family 6: Copybook-Driven Record Parsing

Domain:

- enterprise batch records

COBOL concepts:

- copybook layouts,
- level-01 records,
- nested fields,
- fixed offsets.

Migration challenge:

- read or parse the copybook to correctly slice input records.

Failure modes:

- guessed field widths,
- wrong offsets,
- wrong decimal scale,
- ignoring filler fields.

#### Family 7: OCCURS Table Processing

Domain:

- invoice line items or policy riders

COBOL concepts:

- `OCCURS`,
- repeated fixed-width groups,
- loops over arrays.

Migration challenge:

- parse repeated records and aggregate values.

Failure modes:

- wrong stride length,
- wrong item count,
- treating repeated group as a flat string.

#### Family 8: INSPECT TALLYING And REPLACING

Domain:

- data cleaning

COBOL concepts:

- `INSPECT TALLYING`,
- `INSPECT REPLACING`,
- character normalization.

Migration challenge:

- preserve exact character counting and replacement behavior.

Failure modes:

- counting after replacement instead of before,
- replacing too broadly,
- mishandling spaces.

#### Family 9: Date Normalization

Domain:

- claims or billing

COBOL concepts:

- string slicing,
- numeric validation,
- branch logic.

Migration challenge:

- convert legacy date formats while preserving invalid or edge values as specified.

Failure modes:

- overusing Python date parsing,
- rejecting legacy-valid edge cases,
- wrong century/window logic.

#### Family 10: Ledger Balancing

Domain:

- accounting

COBOL concepts:

- signed amounts,
- debit/credit flags,
- running totals,
- final status code.

Migration challenge:

- preserve sign conventions and final status formatting.

Failure modes:

- inverted debit/credit,
- wrong sign,
- float precision,
- wrong balancing threshold.

#### Family 11: Light REDEFINES

Domain:

- record variant parsing

COBOL concepts:

- limited `REDEFINES`,
- record variants based on type code.

Migration challenge:

- parse the same byte span differently depending on a discriminator.

Failure modes:

- parsing all variants at once,
- wrong discriminator,
- wrong field overlap.

This should be a later family because it is easier to get wrong.

#### Family 12: Multi-Paragraph Flow

Domain:

- generic business workflow

COBOL concepts:

- paragraphs,
- `PERFORM THRU`,
- shared working-storage state.

Migration challenge:

- preserve procedural control flow across multiple paragraphs.

Failure modes:

- wrong execution order,
- missing side effects,
- returning too early.

This should be a later family.

### 6.5 Business Realism

Each family should be wrapped in a realistic business ticket.

Bad task framing:

> Convert this COBOL snippet into Python.

Good task framing:

> The payroll batch job emits incorrect net-pay records after a modernization attempt. Migrate the tax calculation from `PAYTAX.cbl` into Python. Preserve fixed-width output and decimal rounding because downstream ACH generation consumes exact positions.

The story matters for judging.

### 6.6 Compiled Task Bank

Source family definitions should compile into frozen task artifacts.

Recommended files:

```text
server/task_families/
  decimal_payroll.py
  fixed_width_customer.py
  invoice_totals.py
  claims_eligibility.py
  copybook_records.py

server/compiled_tasks/
  train.jsonl
  val.jsonl
  test.jsonl
  manifest.json
```

Compiled tasks should include enough data for deterministic environment replay but must not expose hidden answers to the client.

---

## 7. Data Splits And Generalization

### 7.1 Split Types

Use multiple split axes.

Family split:

- train families,
- validation families,
- held-out test families.

Parameter split:

- seen family but unseen widths,
- unseen numeric ranges,
- unseen branch thresholds,
- unseen copybook field names,
- unseen record lengths.

Template split:

- same semantic concept but different COBOL template.

Human-authored split:

- a small number of manually authored realistic tasks not generated by the same templates.

### 7.2 Recommended Split Strategy

For a strong first version:

- Train: 6 to 8 families
- Validation: 1 to 2 families
- Test: 2 to 3 families
- Human-authored challenge set: 5 to 10 tasks

For each train family:

- include parameter-held-out tests.

For each held-out family:

- include hidden and fresh tests.

### 7.3 Why This Matters

Random instance splits are not enough. If train and test share the same template, the model may learn the template instead of the underlying migration skill.

The evaluation should answer:

- Did the agent improve on seen task families?
- Did it generalize to new parameters?
- Did it generalize to new templates?
- Did it generalize to unseen semantic families?
- Did it handle more realistic human-authored examples?

---

## 8. Reward Design

### 8.1 Reward Philosophy

The reward must teach the actual task:

- migrate safely,
- preserve behavior,
- use tools when useful,
- avoid shortcuts,
- produce executable Python.

The final public score should emphasize semantic correctness. Process rewards should help training but should not dominate the headline metric.

### 8.2 Reward Components

Recommended final reward:

```python
final_reward = (
    0.55 * r_hidden_correctness
    + 0.15 * r_fresh_correctness
    + 0.10 * r_interface_contract
    + 0.08 * r_type_and_layout_fidelity
    + 0.07 * r_anti_hardcoding
    + 0.05 * r_safety
)
```

Training-only shaping reward:

```python
training_reward = final_reward + capped_process_shaping
```

Process shaping should not be used as the main reported score.

### 8.3 `r_hidden_correctness`

Measures pass rate on frozen hidden tests.

Properties:

- deterministic,
- comparable across runs,
- not visible to the agent,
- reported in evaluation.

### 8.4 `r_fresh_correctness`

Measures pass rate on newly sampled tests from the family generator.

Purpose:

- reduce hardcoding,
- test generalization,
- catch memorized visible examples.

Fresh tests should use seeds not included in compiled visible or hidden sets.

### 8.5 `r_interface_contract`

Checks:

- Python parses,
- required callable exists,
- expected function name exists,
- callable accepts expected input,
- callable returns expected output type,
- no stdout/stderr side effects on import,
- no module-level execution that performs unsafe actions.

Allow helper functions. Do not require exactly one top-level function.

### 8.6 `r_type_and_layout_fidelity`

Checks:

- decimal behavior where required,
- fixed-width output lengths,
- zero padding,
- space padding,
- field alignment,
- sign handling,
- implied decimal scale,
- output record width,
- copybook field offset behavior.

This reward should use runtime probes, not only AST checks.

### 8.7 `r_anti_hardcoding`

Checks:

- fresh generated inputs,
- mutated constants,
- branch thresholds not in visible tests,
- unseen record values,
- randomized field names where possible,
- edge values around boundaries.

The model should not receive high reward by memorizing visible examples.

### 8.8 `r_safety`

Checks:

- no forbidden imports,
- no filesystem access outside sandbox,
- no network,
- no subprocess,
- no reflection abuse,
- no excessive CPU,
- no excessive memory,
- no timeout,
- no environment variable access,
- no mutation of protected harness state.

Unsafe code should receive zero or near-zero reward.

### 8.9 Process Shaping

Training-only process shaping can include:

- read required COBOL file before final submission,
- read copybook on copybook-dependent tasks,
- parsed copybook layout when field offsets matter,
- ran visible tests before final submission,
- inspected diff after visible failure,
- improved visible pass rate after a draft,
- avoided repeated identical failing submissions.

Example:

```python
capped_process_shaping = min(
    0.10,
    0.02 * read_required_sources
    + 0.02 * used_required_copybook
    + 0.02 * ran_visible_tests
    + 0.02 * inspected_relevant_diff
    + 0.04 * visible_pass_rate_improved
)
```

Important:

- Do not reward tool clicking by itself.
- Reward only task-relevant tool use.
- Keep shaping capped.
- Report final correctness separately.

### 8.10 Failure Taxonomy

Every failed evaluation should be tagged.

Recommended categories:

- syntax error,
- missing callable,
- wrong output type,
- timeout,
- unsafe code,
- decimal precision,
- rounding,
- fixed-width length,
- padding/truncation,
- sign handling,
- branch precedence,
- loop bounds,
- copybook offset,
- `OCCURS` stride,
- level-88 condition,
- hardcoding suspected,
- unknown runtime failure.

This helps debugging and makes the writeup more credible.

---

## 9. Sandbox And Security

The environment executes model-generated Python. Treat sandboxing as a core part of the system.

### 9.1 Security Goals

The generated code must not be able to:

- read secrets,
- access the network,
- write outside a temporary directory,
- spawn subprocesses,
- inspect the host system,
- modify the test harness,
- persist state across episodes,
- run indefinitely,
- consume excessive memory.

### 9.2 Recommended Execution Model

For each draft evaluation:

- create an isolated temporary directory,
- write candidate code to a file,
- run it in a subprocess,
- run all test cases for that evaluation inside that subprocess,
- apply timeout,
- apply memory limit,
- apply CPU limit if available,
- clear environment variables,
- disable network at the container or process level where possible,
- capture stdout/stderr,
- delete the temporary directory after execution.

### 9.3 Python Restrictions

Use multiple layers:

- AST scan before execution,
- import allowlist,
- blocked builtins,
- runtime guard wrapper,
- subprocess isolation,
- OS resource limits,
- container-level isolation where possible.

Blocked or restricted:

- `os`,
- `sys` where unsafe,
- `subprocess`,
- `socket`,
- `pathlib` if filesystem access is not needed,
- `open`,
- `eval`,
- `exec`,
- `compile`,
- `globals`,
- `locals`,
- `vars`,
- `__import__`,
- reflection on frame objects.

Allowed imports can include:

- `decimal`,
- `datetime` for date families,
- `re` if needed,
- `math` if safe,
- `typing` if needed.

Keep the allowlist small.

### 9.4 No Secrets In Environment

Do not pass API keys, tokens, HF credentials, or private paths into the sandbox environment.

### 9.5 Determinism

Evaluation should be deterministic for frozen tests:

- fixed seeds,
- stable test order,
- stable decimal context,
- no wall-clock dependence,
- no randomness unless seeded by the environment.

---

## 10. Training Pipeline

### 10.1 Training Goal

The goal is to show that training improves agent behavior inside the environment.

The demo does not need to prove full industrial COBOL modernization. It needs to prove:

- the environment is trainable,
- reward is meaningful,
- the model improves from baseline,
- the trained model uses tools and feedback better.

### 10.2 Model Strategy

Use open-source models for TRL or Unsloth training.

Recommended ladder:

- small model for environment plumbing,
- medium model for first real training,
- larger model for final run if compute allows.

Do not depend on the largest model for the minimum result. A small or medium model with clear improvement is better than a large model with unclear training evidence.

If external API calls are used for optional synthetic data generation, stronger-model assistance, or documentation drafting, route them through Azure OpenAI and prefer `gpt-5.4`. Do not put external API calls in the live environment reward path.

### 10.3 Baseline Run

Before training, run baseline inference on:

- train tasks,
- validation tasks,
- held-out tasks,
- one demo task.

Capture:

- total reward,
- hidden pass rate,
- fresh pass rate,
- tool-use behavior,
- failure categories,
- representative trajectories.

### 10.4 Trace Generation

Generate tool-use traces for light SFT warm start.

Trace types:

- ideal trace,
- debugging trace,
- copybook-inspection trace,
- wrong-first-then-fix trace,
- minimal-tool successful trace,
- failed trace with explanation if useful.

Do not generate SFT traces for held-out test families.

Avoid traces that simply reveal the reference implementation. The trace should show how to use the workbench, not memorize answers.

### 10.5 SFT Warm Start

Purpose:

- teach action formatting,
- teach tool-call rhythm,
- teach when to inspect files,
- teach how to revise after tests.

SFT should be small and targeted. It should not replace RL.

### 10.6 GRPO / RLVR Training

Use TRL or Unsloth with verifiable rewards.

The training loop should:

- sample one or more tasks,
- generate actions from the model,
- execute them through OpenEnv,
- compute reward,
- update the model using GRPO or equivalent RLVR method,
- log reward components,
- periodically sample trajectories for inspection.

### 10.7 Curriculum

Use curriculum learning.

Phase 1:

- simple families,
- short episodes,
- forgiving visible tests,
- more process shaping.

Phase 2:

- copybook and decimal families,
- longer episodes,
- lower process shaping,
- more hidden correctness weight.

Phase 3:

- held-out-style templates,
- fresh tests,
- realistic business tasks,
- final evaluation.

### 10.8 Training Metrics

Log:

- total reward,
- hidden correctness,
- fresh correctness,
- interface correctness,
- type/layout fidelity,
- safety failures,
- timeout rate,
- visible pass rate,
- number of tool calls,
- copybook-read rate on copybook tasks,
- diff-use rate after failures,
- final submission rate,
- average episode length,
- failure taxonomy counts.

Do not rely on one scalar reward plot.

### 10.9 Save And Test Models

After training:

- save adapters or merged model correctly,
- immediately test inference,
- run evaluation script from a clean process,
- compare baseline and trained model on the same task set,
- save plots and outputs.

For QLoRA or LoRA, avoid naive merge paths that damage model quality. Use the recommended save method for the chosen training stack.

---

## 11. Evaluation Plan

### 11.1 Required Comparisons

At minimum, compare:

- baseline model,
- SFT-warm-started model if used,
- RL-trained model.

Recommended table:

```text
Model                  Hidden Pass   Fresh Pass   Safety Fail   Avg Reward
Baseline               0.18          0.12         0.04          0.31
SFT                    0.24          0.18         0.02          0.39
SFT + GRPO             0.39          0.33         0.01          0.55
```

Use real numbers from runs. The table above is only a format example.

### 11.2 Evaluation Slices

Report results by:

- all tasks,
- seen families,
- parameter-held-out tasks,
- template-held-out tasks,
- family-held-out tasks,
- copybook-dependent tasks,
- decimal-sensitive tasks,
- human-authored challenge tasks.

### 11.3 Qualitative Examples

Include at least three short case studies:

- Tier 1: simple decimal or fixed-width migration.
- Tier 2: copybook-driven record parsing.
- Tier 3: multi-step workflow with debugging.

For each:

- show baseline behavior,
- show trained behavior,
- show reward difference,
- explain the important failure or improvement.

### 11.4 Plots

Commit readable plots:

- reward over training steps,
- hidden vs fresh pass rate,
- baseline vs trained by family,
- failure taxonomy before vs after,
- tool-use behavior before vs after.

Every plot should have:

- labeled x-axis,
- labeled y-axis,
- legend,
- one-line caption in README.

### 11.5 Anti-Hacking Evaluation

Run checks for:

- visible-example memorization,
- hardcoded input values,
- hardcoded output strings,
- forbidden imports,
- timeout exploitation,
- environment state mutation,
- repeated identical tool-call loops.

Include a short "safeguards" section in the README.

---

## 12. Demo And Storytelling

### 12.1 Judge-Facing Story

Use this framing:

> We simulate the work of a legacy modernization engineer. The agent receives a migration ticket, inspects COBOL and copybooks through tools, writes Python, runs tests, debugs failures, and submits a final migration. Training improves the agent's ability to use the workbench and preserve business behavior under hidden tests.

### 12.2 Recommended 2-Minute Video Structure

0:00 to 0:15:

- "Critical business logic still lives in COBOL. Migration is risky because fixed-width records, decimal arithmetic, and copybooks encode hidden behavior."

0:15 to 0:35:

- Show the OpenEnv workbench.
- Show available files and tools.

0:35 to 1:05:

- Baseline model attempt.
- It ignores copybook or submits early.
- Visible/hidden tests fail.

1:05 to 1:35:

- Trained model attempt.
- It reads COBOL, parses copybook, runs tests, inspects diff, revises.

1:35 to 1:50:

- Show reward curve and baseline-vs-trained table.

1:50 to 2:00:

- Close with: "This is a trainable professional tool-use environment for legacy modernization."

### 12.3 README Structure

Recommended README:

```text
# Legacy COBOL Migration Workbench

## What Problem We Solve
Explain legacy modernization and why one-shot translation is not enough.

## Environment Overview
What the agent sees, what tools it can call, what ends an episode.

## Task Families
Brief table of supported COBOL/business task families.

## Rewards
Composable reward components and anti-hacking safeguards.

## Training
TRL/Unsloth script, model used, run details.

## Results
Reward curves, baseline-vs-trained table, qualitative examples.

## Demo
Link to Hugging Face Space and video/blog.

## Reproducing
Install, run environment, run evaluation, run training script.
```

### 12.4 Space Demo

The Hugging Face Space should let judges:

- reset an episode,
- inspect the migration ticket,
- view available files,
- execute tool actions,
- run a baseline sample,
- run a trained sample if available,
- see reward components,
- see hidden score summary after final submission.

The Space does not need to expose all internals, but it should be easy to understand in under one minute.

---

## 13. Repository Structure

Recommended structure:

```text
.
|-- README.md
|-- openenv.yaml
|-- pyproject.toml
|-- server/
|   |-- app.py
|   |-- environment.py
|   |-- models.py
|   |-- rewards.py
|   |-- sandbox.py
|   |-- metrics.py
|   |-- tools.py
|   |-- task_bank.py
|   |-- task_families/
|   |   |-- __init__.py
|   |   |-- decimal_payroll.py
|   |   |-- fixed_width_customer.py
|   |   |-- invoice_totals.py
|   |   |-- claims_eligibility.py
|   |   |-- level88_status.py
|   |   |-- copybook_records.py
|   |   |-- occurs_tables.py
|   |   `-- inspect_transform.py
|   `-- compiled_tasks/
|       |-- manifest.json
|       |-- train.jsonl
|       |-- val.jsonl
|       `-- test.jsonl
|-- client/
|   |-- __init__.py
|   `-- client.py
|-- authoring/
|   |-- compile_task_bank.py
|   |-- validate_family.py
|   |-- parity_check.py
|   |-- generate_human_challenges.py
|   `-- stress_test_env.py
|-- training/
|   |-- generate_traces.py
|   |-- sft_warmstart.py
|   |-- grpo_train.py
|   |-- evaluate.py
|   `-- colab_notebook.ipynb
|-- eval/
|   |-- run_baseline.py
|   |-- run_trained.py
|   |-- compare_results.py
|   `-- failure_taxonomy.py
|-- plots/
|   |-- reward_curve.png
|   |-- hidden_vs_fresh.png
|   |-- baseline_vs_trained.png
|   `-- failure_taxonomy.png
|-- examples/
|   |-- demo_ticket.md
|   |-- baseline_trace.json
|   `-- trained_trace.json
`-- docs/
    |-- cobol_subset.md
    |-- reward_design.md
    |-- sandbox_design.md
    `-- video_script.md
```

---

## 14. Implementation Phases

This section is ordered by dependency, not by calendar time.

### Phase 1: Define The Spec

Deliverables:

- COBOL subset document,
- Python interface spec,
- task-family schema,
- reward component definitions,
- environment action schema,
- sandbox requirements.

Exit criteria:

- someone can read the spec and know exactly what the environment supports.

### Phase 2: Build One End-To-End Task

Deliverables:

- one task family,
- one compiled task instance,
- `reset`,
- `step`,
- `state`,
- `read_cobol_file`,
- `write_python_solution`,
- `run_visible_tests`,
- `submit_final`,
- basic reward.

Exit criteria:

- a hand-written Python solution can pass hidden tests through the environment.

### Phase 3: Add Copybook Tooling

Deliverables:

- raw copybook reader,
- copybook parser,
- layout inspection output,
- at least one copybook-dependent family.

Exit criteria:

- a solution that ignores the copybook fails,
- a solution that uses layout information can pass.

### Phase 4: Harden The Sandbox

Deliverables:

- subprocess runner,
- timeout,
- memory cap,
- import allowlist,
- blocked builtins,
- temp directory isolation,
- safety reward,
- tests for malicious submissions.

Exit criteria:

- common exploit attempts fail safely.

### Phase 5: Expand Task Families

Deliverables:

- 6+ high-quality task families,
- visible/hidden/fresh tests,
- compiled train/val/test splits,
- parity checks,
- failure taxonomy tags.

Exit criteria:

- task bank can be evaluated deterministically.

### Phase 6: Add Training Pipeline

Deliverables:

- baseline script,
- trace generator,
- SFT warm-start script if used,
- GRPO training script,
- evaluation script,
- plots.

Exit criteria:

- training script runs against the live OpenEnv environment and produces reward logs.

### Phase 7: Package For Judges

Deliverables:

- Hugging Face Space,
- README,
- plots,
- short video/blog/slides,
- demo traces,
- reproducibility instructions.

Exit criteria:

- a judge can open the README, understand the idea in 3 to 5 minutes, run the Space, and see evidence of training improvement.

---

## 15. OpenEnv-Specific Requirements Checklist

The submission must satisfy:

- uses latest OpenEnv release available during development,
- implements OpenEnv environment interface,
- provides `reset`,
- provides `step`,
- provides `state`,
- has valid `openenv.yaml`,
- respects client/server separation,
- does not use reserved MCP tool names,
- hosted on Hugging Face Spaces,
- environment URL included in README,
- training script uses TRL or Unsloth,
- training script connects to the environment,
- evidence of actual training is included,
- reward and loss plots are committed,
- README explains problem, environment, rewards, and results,
- video/blog/slides are linked from README,
- repository avoids large video files.

---

## 16. Engineering Quality Checklist

Environment:

- deterministic reset with seed,
- clear action validation,
- useful error messages,
- bounded episode length,
- no infinite loops,
- metrics emitted for every episode,
- visible tests cannot access hidden answers,
- hidden tests are not sent to client,
- fresh tests use independent seeds.

Rewards:

- multiple independent reward components,
- no single brittle reward,
- hidden correctness reported separately,
- process shaping capped,
- safety failures penalized,
- anti-hardcoding tests included.

Sandbox:

- timeout enforced,
- memory limit enforced,
- imports restricted,
- filesystem restricted,
- network disabled,
- secrets absent,
- subprocess cleanup works,
- exploit tests included.

Training:

- baseline captured,
- training logs saved,
- generated samples inspected,
- reward hacking checked,
- model save path tested,
- final evaluation run from clean process.

Demo:

- one clear narrative example,
- before/after model behavior,
- readable plots,
- concise video,
- README links all materials.

---

## 17. Known Risks And Mitigations

### Risk: The Environment Becomes A Static Translation Benchmark

Mitigation:

- keep observations partial,
- require tool-mediated file inspection,
- include copybook-dependent tasks,
- include visible-test debugging,
- report tool behavior.

### Risk: Reward Hacking Through Tool Rituals

Mitigation:

- keep final score correctness-heavy,
- cap process shaping,
- reward only task-relevant tool use,
- report correctness separately.

### Risk: Generated Tasks Feel Too Synthetic

Mitigation:

- wrap tasks in business tickets,
- use realistic domains,
- add human-authored challenge tasks,
- include copybooks and fixed-width records.

### Risk: COBOL Semantics Are Ambiguous

Mitigation:

- document the supported subset,
- use one compiler/runtime oracle when possible,
- add parity checks,
- require human review for each family.

### Risk: Sandbox Is Exploited

Mitigation:

- use layered restrictions,
- test malicious submissions,
- isolate every run,
- do not expose secrets,
- terminate unsafe code early.

### Risk: Model Gets Sparse Reward

Mitigation:

- start with easy families,
- use visible tests,
- use SFT for tool formatting,
- use curriculum,
- shape process reward lightly.

### Risk: Training Curves Improve But Behavior Is Bad

Mitigation:

- inspect generated trajectories,
- log reward components,
- track failure taxonomy,
- run fresh tests,
- include qualitative examples.

---

## 18. Suggested Judge-Facing Metrics

Use these in README and video:

```text
Metric                               Baseline   Trained
Overall reward                       ...
Hidden test pass rate                ...
Fresh test pass rate                 ...
Copybook task pass rate              ...
Decimal-sensitive task pass rate     ...
Safety failure rate                  ...
Average visible-test improvement     ...
Useful tool-use rate                 ...
```

Also include:

- reward curve,
- hidden/fresh pass curve,
- baseline-vs-trained bar chart,
- one representative trace.

### 18.1 Useful Tool-Use Rate

Define carefully:

```text
Useful tool-use rate =
number of task-relevant tool calls that contributed to later improvement
divided by
number of opportunities where that tool was relevant
```

Do not count meaningless tool calls as useful.

---

## 19. Recommended First Demo Task

### 19.1 Business Ticket

Title:

- Payroll Net Pay Migration

Story:

> The payroll batch system emits fixed-width employee net-pay records. The COBOL source uses a copybook to define field offsets and implied decimal salary fields. Migrate the calculation into Python while preserving exact fixed-width output because the downstream ACH export depends on byte positions.

Files:

- `PAYROLL.cbl`
- `EMPLOYEE_PAY.cpy`

Important traps:

- `GROSS-PAY` is `9(7)V99`,
- deductions are signed,
- tax rate uses implied decimal scale,
- output net pay is zero-padded cents,
- employee name is space-padded to fixed width.

Why it is good:

- easy for judges to understand,
- copybook matters,
- decimal behavior matters,
- visible diff is intuitive,
- hidden tests can catch hardcoding.

### 19.2 Baseline Failure

Baseline model likely:

- ignores copybook,
- treats decimal string as float,
- emits `123.45` instead of `0000012345`,
- trims spaces,
- submits early.

### 19.3 Trained Success

Trained model should:

- read COBOL,
- read copybook,
- parse layout,
- write first draft,
- run visible tests,
- inspect diff,
- fix padding and decimal conversion,
- submit final code.

This is the core demo.

---

## 20. Final Definition Of Done

The project is submission-ready when:

- OpenEnv environment runs locally,
- Hugging Face Space is live,
- `openenv.yaml` is valid,
- at least 6 task families are validated,
- hidden and fresh tests work,
- sandbox blocks obvious exploits,
- baseline evaluation is saved,
- trained evaluation is saved,
- reward plots are committed,
- README tells the story clearly,
- video/blog/slides are linked,
- one demo trace is polished,
- training script is runnable,
- final model or adapter can be loaded for inference,
- no hidden answers are exposed to the client.

---

## 21. Final Recommendation

Build this as a professional world-modeling environment, not a translation dataset.

The strongest version is:

- COBOL-subset-defined,
- copybook-aware,
- tool-mediated,
- sandboxed,
- hidden/fresh-test verified,
- trainable through OpenEnv,
- demonstrated with baseline-vs-trained improvement,
- explained as safe legacy modernization.

The judging story should be simple:

> The agent learns to use a migration workbench like a legacy modernization engineer. After training, it reads the right files, uses the right tools, debugs failures, and preserves business behavior more reliably than the baseline.
