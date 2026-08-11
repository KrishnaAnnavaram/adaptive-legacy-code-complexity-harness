---
name: configuration-complexity
description: >
  How much of the system's behaviour is decided OUTSIDE the source code, and
  how tangled that external surface is. In legacy estates configuration is
  where behaviour hides. The same program behaves differently per region,
  per environment, per compile flag - and none of that is visible to any
  metric that only reads the code. It is also the leading cause of migration
  failures that pass every test and then break in production, because the
  new platform's configuration surface was never mapped.
  Implemented deterministically by `.claude/complexities/18_configuration_complexity.py`; used by the Complexity Agent (1_complexity) in tier band 5 (hazard).
---

# 18 - Configuration Complexity

## Purpose

**What it measures.** How much of the system's behaviour is decided OUTSIDE the source code, and how tangled that external surface is.

**Why it matters.** In legacy estates configuration is where behaviour hides. The same program behaves differently per region, per environment, per compile flag - and none of that is visible to any metric that only reads the code. It is also the leading cause of migration failures that pass every test and then break in production, because the new platform's configuration surface was never mapped.

## Method

Measures four things that pull in opposite directions: 1. EXTERNAL SURFACE - config keys, env vars, feature flags. More surface = more environment-dependent behaviour. 2. BUILD VARIANTS   - conditional compilation. Each flag doubles the number of programs that actually exist. 3. HARDCODING       - values that SHOULD be config but are literals. The inverse problem: nothing to configure, so every change is a code change. 4. SCATTER          - config read in many places rather than loaded once. Scatter is what makes config changes unreviewable. Both too much and too little externalization are penalised, because both make change expensive.

## Input contract

| Field | Requirement | Behaviour if absent |
|---|---|---|
| `units` | **Required** | Absent -> `insufficient_input`, analyzer never runs |
| `config_reads`, `literals`, `conditional_compilation`, `feature_flags` | **At least one** | None present -> `insufficient_input` |
| `dependency_graph` | Optional | Absent -> confidence reduced, reason recorded |
| `loc` | Optional | Absent -> confidence reduced, reason recorded |

- **Scope:** unit
- **Tier band:** 5 (hazard)
- **Depends on:** none
- **Direction:** `higher_is_worse`

### Tree fields consumed

```
tree = {
  "language": "java",
  "units": [ {
      "id","name","owner_type","loc",
      "config_reads": [ {"key":str,"source":"file|env|db|arg|registry|copybook",
                         "line":int,"default":bool}, ... ],
      "feature_flags": [ {"name":str,"line":int}, ... ],
      "conditional_compilation": [ {"flag":str,"line":int}, ... ],
      "literals": [ {"value":str,"kind":"number|string|path|url|connection|credential",
                     "line":int}, ... ],
      "cfg": {"node_type","children":[...]}
  }, ... ],
  "dependency_graph": {"edges":[{"from","to","kind":"config"}, ...]}   # optional
}
```

## Language Neutrality

An adapter maps whatever the parser found onto these lists:
    PL/SQL   $$ccflags -> conditional_compilation; parameter tables -> config_reads
    COBOL    COPY REPLACING -> conditional_compilation; SYSIN/JCL PARM,
             ACCEPT FROM ENVIRONMENT -> config_reads
    Java     @Value / System.getProperty / System.getenv -> config_reads;
             build profiles -> conditional_compilation
The scoring rules never reference a language.

## Output structure

Returns the uniform envelope defined in [`docs/analyzer-contract.md`](../../../docs/analyzer-contract.md):

```json
{
  "contract_version": "2.0",
  "id": "configuration_complexity",
  "sno": 18,
  "complexity": "Configuration Complexity",
  "tier": "hazard",
  "status": "ok | insufficient_input | error",
  "summary": { "level": "L1..L5", "score": 0.0, "headline": "..." },
  "metrics": { },
  "hotspots": [ ],
  "items": [ ],
  "confidence": { "score": 1.0, "reasons": [] },
  "inputs_used": [ ],
  "inputs_missing_optional": [ ]
}
```

## Levels

| Level | Meaning |
|---|---|
| `L1` | trivial |
| `L2` | low |
| `L3` | moderate |
| `L4` | high |
| `L5` | severe |

## Error handling

| Condition | Severity | Action |
|---|---|---|
| A required input is absent | - | Return `insufficient_input` naming the field. **Never return a zero** - a clean zero from a starved analyzer is indistinguishable from a genuine clean result. |
| An optional input is absent | `warning` | Run in degraded mode; confidence reduced and the reason recorded in `confidence.reasons` |
| Tree contains no units | - | Return `insufficient_input` |
| Unhandled exception | `error` | Caught by `_core.run()`, returned as `status: error` with the exception text. The pipeline continues. |

## Invocation

```bash
python .claude/complexities/18_configuration_complexity.py TREE.json
python .claude/complexities/18_configuration_complexity.py TREE.json -o report.json
cat TREE.json | python .claude/complexities/18_configuration_complexity.py
python .claude/complexities/18_configuration_complexity.py --spec
```
