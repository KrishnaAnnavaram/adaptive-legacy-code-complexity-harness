# adaptive-legacy-code-complexity-harness

Adaptive, language-aware harness for identifying legacy source code, selecting applicable
complexity analyses, orchestrating execution, generating traceable metric-level reports,
and consolidating results into a unified code complexity artifact.

**Input:** a parser tree — an ANTLR parse tree, an AST, or an upstream parser artifact.
**Output:** one unified, traceable code complexity artifact.
**Architecture:** a single agent, five skills, and a plugin library you extend over time.

---

## What it does

One agent carries a parse tree end to end through seven phases:

| # | Phase | Question answered |
|---|---|---|
| 1 | **Comprehend** | What language is this tree, what constructs does the code contain, and what can this tree actually support analytically? |
| 2 | **Decide** | Which complexity analyses apply to *this* language, *this* architecture, and *this* code? |
| 3 | **Resolve** | What does the versioned knowledge base say is mandatory vs. recommended here? |
| 4 | **Order** | What is the correct professional execution sequence? |
| 5 | **Execute** | Run each complexity script; write one separate, traceable result document per metric. |
| 6 | **Verify** | Is the result set complete? Which mandatory metrics did not succeed? |
| 7 | **Consolidate** | Merge everything into one unified artifact. |

Tree generation is **not** in scope — that is handled by upstream inventory and parser
agents. This harness starts where they finish.

---

## Two design commitments

Everything else follows from these.

### Never fabricate a measurement

Every plugin declares the tree capabilities it needs. The runner checks them **before
invoking the script**. A metric whose inputs are unavailable reports `not_computable`
with the missing capability named — it is never approximated.

This is not theoretical. During development the harness was run against real
`plsql-to-brd` output and found that the upstream `LOGGER.json` CFG is *summarised*: all
65 members reduced to `ENTRY → BLOCK → EXIT_POINT`, with no `IF`/`CASE`/`LOOP` nodes and
no `depth`. An earlier build of the adapter reported:

```
LOGGER   max cyclomatic complexity = 2   band = low
```

For a 65-member package that reads as *simple code* and is purely an artifact of the
input. The capability probe was tightened; it now reports:

```
LOGGER              cyclomatic_complexity  not_computable
                    reason: NTM lacks has_decision_points
                    warning: upstream CFG is summarised — re-run the parser at
                             full CFG fidelity to recover branch metrics

LOGGER_CONFIGURE    cyclomatic_complexity  v(G)=8  band=low  confidence=0.75
```

A plausible wrong number is worse than an honest gap, because nobody can tell it is
wrong.

### Never lose traceability

Every score traces to a result document → an NTM element → a node of the original tree.
Each NTM records the `tree_path` and grammar rule behind every element, plus a
`coverage_ratio`; below 0.80, downstream metric confidence is capped at that ratio
automatically.

---

## The 20 complexity analyzers

All analyzers are language-agnostic by construction — they consume a canonical
tree vocabulary, never source text or a dialect. The same script scores COBOL,
PL/SQL and Java.

| # | Analyzer | Measures |
|---|---|---|
| 1–7 | cyclomatic, cognitive, control_flow, coupling, nesting, npath, structural | Core structural metrics |
| 8–14 | cohesion, dependency, change_impact, maintainability, data_flow, inheritance, interface_api | Module and design metrics |
| **15** | **Database** | SQL surface, schema reach, dynamic SQL, transactions, cursors, and N+1 access patterns (SQL inside a loop) |
| **16** | **Testability** | Splits *test burden* (paths to cover) from *test friction* (hidden inputs, side effects, missing seams, non-determinism) |
| **17** | **Runtime** | Growth class per unit — O(1)…O(n³⁺)/O(2ⁿ) — from loop nesting, weighted by what runs inside the loop |
| **18** | **Configuration** | External surface, build variants (2ⁿ per compile flag), hardcoded literals, config scatter |
| **19** | **Migration** *(derived)* | Splits *volume* from *blockers*; maps each unit onto rehost / replatform / refactor / rearchitect / rebuild |
| **20** | **Architectural** | Dependency cycles, Martin instability/abstractness zones, layering violations, hub units |

Three design notes on 15–20 worth knowing:

- **#16 separates burden from friction** because they need opposite remedies. A unit
  with 40 straightforward paths is a day's grind. A unit with 3 paths behind a static
  clock dependency can block characterization testing indefinitely. Reported as
  `tractable` / `laborious` / `blocked` / `hostile`.
- **#17 discounts statically-bounded loops.** A doubly-nested loop over two fixed-size
  arrays is O(1) in practice; reporting it as a scaling risk is a false positive, and
  false positives are what make a metric get ignored. Every item carries `confidence`.
- **#19 splits volume from blockers** because migration effort is *not* proportional to
  complexity. Volume scales with size and shrinks with tooling; blockers do neither. A
  small, high-blocker estate looks cheap and is where programmes overrun.

### One format, enforced

All twenty analyzers now implement a single contract — see
[complexities/CONTRACT.md](complexities/CONTRACT.md). Each is a pure
`analyze(tree) -> dict` with a self-describing `SPEC`, usable three ways without
modification:

```bash
python run_pipeline.py samples/cobol_payroll.tree.json -o out   # all twenty
python complexities/17_runtime_complexity.py tree.json          # standalone
cat tree.json | python complexities/01_cyclomatic_complexity.py # piped
```

```python
from importlib import import_module
mod = import_module("17_runtime_complexity")
report = mod.analyze(tree)          # embedded in any harness
```

The rule that matters most: **an analyzer starved of its declared inputs returns
`insufficient_input` naming the gap — never a zero.** Earlier versions of this repo
returned clean-looking zeros, and one batch printed fully-formed reports built from
hardcoded demo data, when handed input they could not read. Nothing distinguished
that from a genuine clean result.

Ordering is derived, not configured: tier band → dependency depth → sno. Composites
receive the reports they declared as `depends_on`, so #19 Migration is scored from
real upstream findings rather than re-derived guesses.

```
measured 20/20 (100%)   not measured: 0   errors: 0
overall level L5   hotspots 3
```

### Audited, not asserted

[tools/judge.py](tools/judge.py) runs ten adversarial checks per analyzer — contract
conformance, starvation behaviour, determinism, evidence behind severe scores,
honest input declaration. On its first run it found two real defects in analyzers
#18 and #19: both read line counts they never declared, and #18 treated an unknown
line count as maximal scatter, manufacturing a finding out of missing data. Both fixed.

```bash
python tools/judge.py samples/cobol_payroll.tree.json --self-test
# 20 pass   0 minor   0 CRITICAL
# self-test OK: canary correctly flagged CRITICAL
```

`--self-test` also audits `tools/99_canary_complexity.py`, which is defective on
purpose and **must** come back CRITICAL. A suite that only ever reports PASS tells you
nothing about the code, only about the suite.

> The seven original Style-A analyzers are preserved unmodified in
> [complexities/_superseded_style_a/](complexities/_superseded_style_a/), and
> [tools/tree_bridge.py](tools/tree_bridge.py) still converts a Style-A tree to the
> unified format if you have one.

---

## Architecture

```
                    ANTLR parse tree │ AST JSON │ parser_artifact.json
                                     ▼
                    ┌────────────────────────────────┐
                    │  ADAPTER LAYER  (lib/adapters/) │
                    └────────────────────────────────┘
                                     ▼
                    ╔════════════════════════════════╗
                    ║  NORMALIZED TREE MODEL  (NTM)  ║
                    ║  canonical, language-neutral   ║
                    ╚════════════════════════════════╝
                                     ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  1_complexity agent                                          │
   │                                                              │
   │  P1 comprehend ─► P2/3 select ─► P4 order ─► P5/6 run ─► P7  │
   │       │                │              │           │       │  │
   │  tree-compre-     complexity-    execution-  complexity- artifact-
   │  hension          selector       planner     runner      consolidator
   └─────────────────────────────────────────────────────────────┘
              ▲                 ▲                  ▲
       knowledge base     plugin registry    complexity plugins
       (which metrics     (discovered by      (your Python
        for which          scanning)           scripts)
        language)
                                     ▼
                       complexity_artifact.json
```

### The Normalized Tree Model is the keystone

An ANTLR parse tree and an AST are radically different shapes. A CST is deep, verbose,
named after grammar rules, and **contains no control-flow graph** — a single PL/SQL `IF`
threads through a dozen expression-precedence nodes. An AST from `plsql-to-brd` arrives
already semantic, with a typed CFG.

Adapters project both into one canonical model, and **declare what survived the
projection**:

| Input | `has_cfg` | `has_token_stream` | Consequence |
|---|---|---|---|
| ANTLR CST | `false` | `true` | Halstead works; essential complexity does not |
| plsql-to-brd AST | `true` | `false` | Essential complexity works; Halstead does not |

Complexity plugins are written against the **NTM only** — never against a raw tree.
That is what makes one `cyclomatic_complexity` script work across PL/SQL, COBOL and Java.

---

## Adaptive selection

Selection responds to three independent layers, not one:

| Layer | Source | Example effect |
|---|---|---|
| **Language rules** | `languages.<id>.complexities` | `plsql` → 11 mandatory, 13 recommended |
| **Legacy-model overlay** | `legacy_model_overlays` | `stored_procedure_db` promotes `transaction_boundary_complexity` to mandatory |
| **Construct & hazard triggers** | the actual census of *this* tree | census `dynamic_sql = 12` fires `CT-002` → `dynamic_sql_risk` mandatory |

The third layer is what makes the harness *adaptive*. Two PL/SQL packages from the same
schema get different metric sets if one uses cursors and dynamic SQL and the other does
not. Promotion is monotonic — a trigger can only ever raise a classification, never
weaken a language rule.

Selection also records **what it decided not to run, and why** — `language_not_applicable`,
`capability_missing`, `below_min_routines`. An exclusion with a stated reason is a
materially different claim from silence.

### Zero is a result

Rule `CT-012` makes `exception_handling_completeness` **mandatory when the census finds
zero exception handlers**. The instinct to skip a metric when the construct is absent is
exactly wrong here: a 4,000-line package with no handler anywhere is one of the strongest
risk signals available, and skipping the metric deletes the finding.

---

## Repository layout

```
agents/
  1_complexity_agent.md            ← THE single agent: role, inputs, 7-phase execution order
skills/
  SKILL_tree_comprehension.md      ← P1  tree → NTM, language ID, capability probe, census
  SKILL_complexity_selector.md     ← P2/3 plugin discovery, knowledge base, triggers
  SKILL_execution_planner.md       ← P4  banding, dependency DAG, deterministic sort
  SKILL_complexity_runner.md       ← P5/6 subprocess contract, isolation, verification
  SKILL_artifact_consolidator.md   ← P7  merge, composite risk, hotspots, report
knowledge/
  language_complexity_matrix.json  ← 16 languages, 9 legacy models, 18 triggers, weightings
  complexity_knowledge_base.md     ← the reasoning behind the matrix
  antlr_rule_profiles.json         ← grammar rule-name patterns (plsql, cobol, java, generic)
contracts/
  normalized_tree_model.schema.json
  complexity_plugin.schema.json
  complexity_result.schema.json
  complexity_artifact.schema.json
lib/
  ntm.py                           ← helper API every plugin imports
  adapters/
    plsql_ast_adapter.py           ← plsql-to-brd parser output → NTM
    antlr_adapter.py               ← generic ANTLR CST → NTM
complexities/                      ← THE EXTENSION POINT
  REGISTRY.md                      ← how to add a metric
  _template/                       ← copy this
  source_lines_of_code/
  cyclomatic_complexity/
  decision_density/
tools/
  run_plugin.py                    ← run one plugin standalone
```

---

## Adding a complexity script

This is the part designed to stay easy, because the library grows over time.

```bash
cp -r complexities/_template complexities/my_metric
```

Edit `manifest.json` (id, tier, applicable languages, required capabilities,
thresholds), then write the metric:

```python
from ntm import run

def compute(inp, result):
    for r in inp.ntm.measurable_routines:
        result.add_routine(r, {"my_metric": len(r.branching_decisions)})
    result.aggregate("my_metric", "max")

if __name__ == "__main__":
    run(compute)
```

Add the `metric_id` to the knowledge base, and it is selectable on the next run.

**No agent file changes. No skill changes. No imports to register.** The agent discovers
plugins by scanning `complexities/` and holds no hardcoded metric list anywhere.

A metric the knowledge base requires but for which no plugin exists is reported as a
**knowledge gap** — the harness telling you what to build next. While the library is
being filled in, a non-empty gap list is the expected state.

See [complexities/REGISTRY.md](complexities/REGISTRY.md) for the full contract.

---

## Try it

Against real `plsql-to-brd` output:

```bash
# tree → NTM
python3 lib/adapters/plsql_ast_adapter.py \
    ../plsql-to-brd/output/logger/parser/raw_structure/LOGGER_CONFIGURE.json \
    -o output/ntm/LOGGER_CONFIGURE.ntm.json

# run metrics (order matters — decision_density consumes the first two)
python3 tools/run_plugin.py complexities/source_lines_of_code \
    --ntm output/ntm/LOGGER_CONFIGURE.ntm.json \
    -o output/complexity/source_lines_of_code/LOGGER_CONFIGURE.json

python3 tools/run_plugin.py complexities/cyclomatic_complexity \
    --ntm output/ntm/LOGGER_CONFIGURE.ntm.json \
    -o output/complexity/cyclomatic_complexity/LOGGER_CONFIGURE.json

python3 tools/run_plugin.py complexities/decision_density \
    --ntm output/ntm/LOGGER_CONFIGURE.ntm.json \
    --upstream output/complexity/
```

From an ANTLR tree:

```bash
python3 lib/adapters/antlr_adapter.py tree.json --language plsql \
    -o output/ntm/MY_UNIT.ntm.json
```

Both adapters are verified working against the real `Logger-master` corpus.

---

## Execution order

Bands are absolute:

```
size → structural → data_flow → coupling → hazard → composite → aggregate
```

Within a band: `dependency_level` → `cost_class` → `metric_id`.

- **`size` first** — every later band uses SLOC as a denominator. Computing it once
  centrally stops five plugins from each deriving a different SLOC and disagreeing.
- **`composite` second to last** — `maintainability_index` consumes Halstead, cyclomatic
  and SLOC. It cannot run earlier by construction.
- **Cheap before expensive** — a systemic failure surfaces in seconds, not after an
  exponential path-count run.
- **Alphabetical tie-break** — guarantees a byte-identical plan across runs.

Dependency cycles are a hard configuration error: the agent halts and names the cycle
rather than picking an arbitrary order.

---

## Language coverage

**Specified in depth:** PL/SQL, COBOL.

**Structurally complete, not yet exercised against real corpora:** T-SQL, RPG/RPGLE,
Natural, ABAP, VB6/VBA, PowerBuilder, Informix 4GL, Progress ABL, JCL, SAS, legacy Java,
legacy C/C++, Perl, PL/I, MUMPS.

Thresholds are recalibrated per language, because they have to be. `v(G) = 24` is a
refactoring ticket in Java and unremarkable in a COBOL paragraph — a threshold of 10
flags every production paragraph and therefore discriminates nothing.

| Language | v(G) bands | Why |
|---|---|---|
| Java | 10 / 20 / 50 | Classic McCabe, applies cleanly to structured OO |
| PL/SQL | 10 / 20 / **40** | Top band lowered — above 40 a member cannot be unit-tested in isolation |
| COBOL | **15 / 35 / 75** | Raised throughout; and `essential_complexity` outranks `v(G)` in the weighting, because `ev(G)` decides whether mechanical translation is possible at all |

Adding a language is an edit to `language_complexity_matrix.json` only.

---

## Known limits

Stated plainly so they are not mistaken for oversights.

- **Threshold calibration is judgement, not measurement.** The PL/SQL and COBOL bands
  reflect published practice and field experience, not a statistical study of a reference
  corpus. Re-fit them against your own codebase distribution once enough runs exist.
- **Weighting profiles are policy.** `composite_risk` is only as arguable as its weights.
  They live in the knowledge base, versioned and challengeable, but no weighting is
  objectively correct.
- **Language coverage is uneven.** The fourteen languages beyond PL/SQL and COBOL are a
  solid scaffold, not a finished ruleset.
- **The plugin library is deliberately incomplete.** Three reference implementations ship;
  they exist to prove the contract, not to constitute the suite. The knowledge base names
  ~45 metrics, and every one without a plugin is reported as a knowledge gap.
- **Macro and preprocessor languages are measured pre-expansion.** SAS macro and C
  preprocessor code analysed before expansion describes one variant of many. Plugins are
  required to lower confidence and say so; the underlying limitation is not solved here.
- **The five skills specify behaviour the agent performs; they are not executable code.**
  The adapters, the plugin contract, and the reference metrics are executable and tested.

---

## Upstream and downstream

| Upstream | Supplies | Note |
|---|---|---|
| `plsql-to-brd 2_parser` | `parser_artifact.json` + `raw_structure/*.json` | Richest input — full CFG fidelity where the parser emits it |
| ANTLR-generated parser | parse tree JSON/XML | CST — expect `has_cfg = false` |

| Downstream | Reads | For |
|---|---|---|
| BRD / modernization spec | `complexity_artifact.json`, `hotspots.csv` | Scoping translation effort |
| Migration estimation | `unit_rollup`, `composite_risk` | Effort modelling |
| Refactoring prioritisation | `hotspots[]` with narratives | Ordered remediation backlog |
| Harness maintenance | `knowledge_gaps`, `unmapped_rules` | What to build next |
