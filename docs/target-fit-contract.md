# How the Target-Fit agent stays honest about a language it wasn't given

Companion to [`docs/analyzer-contract.md`](analyzer-contract.md), scoped to
the fourth agent. Its input shape is different on purpose - a Normalized
Tree plus one language descriptor, projected into a second tree, then run
through the same 20 analyzers a second time - so this contract is its own
document rather than an exception carved into the first one.

---

## The shape

```
.claude/target_fit/
  project_tree.py         ← pure function: project_tree(tree, descriptor) -> (projected_tree, log)
  target_fit.py            ← orchestrator: analyze(tree_path, target, languages_dir, source_artifact_path=None)
                              -> (artifact, results); imports run_pipeline.py directly, never duplicates it
  schema.md                 ← what a descriptor must declare
  config.json                 ← optional default target (not yet wired into target_fit.py - see Known gaps)
  languages/
    <lang>.json               ← reviewed, live, read by real runs
    _pending/
      <lang>.json             ← drafted, not yet reviewed, never read by a real run
```

---

## The flow

```
Normalized Tree  +  Target descriptor
        |
        v
  project_tree()  --  drops unexpressible-jump units, drops `types` if no
        |             object model, strips loc/comment_lines/halstead
        v
  Projected Tree   (a second, structurally valid Normalized Tree)
        |
        v
  run_pipeline.discover() / order() / execute() / consolidate()
        |             the SAME functions, the SAME 20 analyzer modules,
        v             Agent 3 already uses - imported, never duplicated
  Target Complexity Artifact  (consolidate()'s own shape)
        |
        v
  + comparison section, built from Agent 3's own complexity_artifact.json
    (read only here, never used to compute a target score above this line)
```

---

## The rule everything here rests on

**A target with no promoted descriptor gets `insufficient_input` naming the
gap, listing what is available. It never gets a guessed profile.**

This is the same rule `.claude/complexities/_core.py` enforces for the 20
complexities, applied one layer up.

---

## The second rule: drafted is not reviewed

Identical to before - a descriptor's `"reviewed"` field is not decoration.
`target_fit.py` halves confidence (`1.0` -> `0.6`) when it is `false`, naming
the reason. A drafted descriptor lives in `languages/_pending/` until
promoted; `target_fit.py` never reads that folder. This applies uniformly -
the four shipped descriptors are not exempt.

---

## The third rule: project, don't guess a score

Earlier versions of this agent read Agent 3's *finished numbers* and either
carried them forward or reweighted them by category. That design is gone.
The current one computes every target score for real, by building a second
tree and running the real analyzers against it - because a source-language
score is not automatically a target-language score, and the only way to get
a genuinely different number where the target genuinely changes something is
to actually measure the projected shape, not reweight the old one.

**Three projection rules, all generic, all descriptor-driven - nothing here
names a specific source or target language:**

1. **Jump constructs.** Any unit whose CFG contains `GOTO`, `ALTER`,
   `PERFORM_THRU` or `FALL_THROUGH` (the exact `JUMP_NODES` set already
   defined once in `_core.py`) is dropped from the projected tree if the
   target descriptor says it can't express that construct
   (`supports_goto` / `supports_alter_style_dynamic_jump`). No mechanical
   rewrite is attempted - a dropped unit's reason is logged in
   `projection.units_dropped`, never silently repaired. A target whose own
   descriptor *does* support the construct (e.g. projecting one COBOL-like
   dialect onto another) keeps the node unchanged.

2. **Object model.** If the target descriptor's `multiple_inheritance` is
   `null` (no class/object model - COBOL and PL/SQL's current descriptors
   both declare this), `types` is dropped from the projected tree entirely.
   Cohesion Complexity (#8) and Inheritance Complexity (#13) then gate to
   `insufficient_input` through the exact same central mechanism
   (`Tree.require(spec)` in `_core.py`) every analyzer already uses for any
   missing required field - no special-casing inside Agent 4 for this.

3. **Volume fields.** `loc`, `comment_lines` and `halstead` are stripped from
   every unit, unconditionally, for every target. There is no honest way to
   project the size of code that does not exist yet, and inventing a
   verbosity/expansion ratio to estimate one is explicitly refused. This
   makes Structural Complexity (#7) and Maintainability Complexity (#11)
   gate the same way - #7 only declares `loc` *optional*, so it still runs
   (degraded confidence, size read from CFG-node counts instead); #11
   declares it *required*, so it gates fully to `insufficient_input`.

Everything else - `references`, `writes`, `globals`, `params`, `meta`,
`sql`, `cursors`, `transactions`, `platform_calls`, `dynamic_constructs`,
`config_reads`, `feature_flags`, `conditional_compilation`, `literals`,
`call_graph`, `dependency_graph` - is a fact about what the code *does*, not
about the language expressing it, and passes through the projection
unchanged.

---

## The one sharp edge: optional fields default toward zero, not toward null

`_core.py`'s central gate only produces a clean `insufficient_input` for a
field an analyzer declares **required**. For a field an analyzer merely
declares **optional** - Migration Complexity's SPEC lists `loc` as optional,
not required - stripping that field doesn't block the analyzer. Its own
internal code (`unit.get("loc", 0)`) then treats the absence as zero and
keeps scoring, while `_core.normalize()`'s existing confidence-degradation
step correctly drops confidence and names `loc` in `confidence.reasons`.

**This means a target score can differ from the source baseline for a
reason that has nothing to do with the target language** - it reflects an
optional field defaulting toward zero inside an already-existing analyzer,
not a genuine reduction in effort. This is not a defect to patch (Agent 4
must not modify the 20 analyzers), and it is not silently hidden either -
`project_tree.py`'s own log carries a `fields_stripped_caveat` entry stating
this plainly, and every comparison delta should be checked against that
specific report's `confidence.reasons` before being read as a real finding.

---

## Known gaps

- **`config.json`'s `default_target_language` is not yet read by
  `target_fit.py`.** `--target` must be passed explicitly on every run.
- **No control-flow restructuring is attempted for dropped units.** A
  provably-correct transformation (e.g. Böhm-Jacopini-style structuring for
  a forward-only skip pattern) could recover a real score for some blocked
  units instead of dropping them outright. This was deliberately deferred -
  a partial or subtly incorrect implementation would produce a *wrong*
  number that looks real, which is worse than the honest `null`/drop this
  version produces. Worth building once there's a concrete blocked-unit case
  to validate it against.
- **No automated judge yet** (unlike `tools/judge.py` for the 20
  complexities). Until one exists, check by hand: `descriptor_reviewed`
  status, that `projection.units_dropped` names real reasons, that
  `comparison` values match a fresh run's own `reports`, and that running the
  same tree/target twice produces byte-identical output (aside from the one
  `generated_at` timestamp `consolidate()` stamps once, same convention
  Agent 3's own artifact already uses).
