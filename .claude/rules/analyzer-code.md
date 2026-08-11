---
paths:
  - ".claude/complexities/**/*.py"
  - ".claude/inventory/**/*.py"
  - "tools/*.py"
---

# Rules for analyzer and tool code

These load only when working on the files above.

- **Standard library only.** No third-party imports. Clients are air-gapped.
- **`analyze(tree) -> dict` is a pure function.** No file IO, no globals, no
  printing, no network. The CLI wraps it, never the reverse.
- **stdout carries the JSON report and nothing else.** Diagnostics go to stderr.
  A stray `print()` corrupts the report and is the most common defect in a new
  analyzer.
- **Never return a zero when input is missing.** Raise `NotComputable` / return
  `insufficient_input` naming the field. A clean zero from a starved analyzer is
  indistinguishable from a genuine clean result.
- **Declare every input you read** in `SPEC.requires` / `requires_any` /
  `optional`. Judge check `C10` fails an analyzer whose score moves when
  undeclared inputs are stripped while confidence stays at 1.0.
- **Deterministic.** No timestamps in an analyzer's own output. No set-iteration
  order leaking into results.
- **Do not band your own output.** The runner applies language-calibrated
  thresholds; a `risk_band` you set is overwritten.

Full contract: @docs/analyzer-contract.md

After any change here, run:

```bash
python .claude/complexities/run_pipeline.py samples/cobol_payroll.tree.json -o out
python tools/judge.py samples/cobol_payroll.tree.json --self-test
```
