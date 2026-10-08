# The writing standard: ASD-STE100 Simplified Technical English

Use these rules for every README and for `docs/ste-style-guide.md` in each repository. Copy this file
into the repository as `docs/ste-style-guide.md` and add a **project vocabulary** section (Section 3)
with the technical names and technical verbs of that project.

## 1. The writing rules

### Words

1. Use one word for one meaning, and one meaning for one word. Do not use synonyms for variety.
2. Use a word only as one part of speech. For example, `test` is a noun or a verb, `check` is a verb.
3. Do not use phrasal verbs (`set up`, `carry out`, `find out`, `pick up`, `look up`, `come up with`).
   Use one verb: `prepare`, `do`, `find`, `get`, `make`.
4. Do not use an `-ing` form as a noun or an adjective (`the running job`, `after indexing`).
   Exception: a technical name, a file name, a command or a status value.
5. Do not use contractions (`don't`, `it's`, `can't`). Do not use slang or idioms
   (`out of the box`, `under the hood`, `at a glance`, `gotcha`, `bells and whistles`).
6. Do not use `and/or`. Write `A, B or both`.
7. Do not use `should`, `could`, `would` or `may` for instructions. Use `must` for a rule, the
   imperative for a step and `can` for a possibility.
8. Keep the articles `a`, `an` and `the` in sentences.
9. Do not make a noun cluster of more than three words. A technical name is one word.

### Sentences

1. A procedural sentence (an instruction) has a maximum of **20 words**.
2. A descriptive sentence has a maximum of **25 words**.
3. Write one instruction in one sentence.
4. Use the imperative for an instruction: `Run the tests.` Not `The tests should be run.`
5. Use the active voice. Use the passive voice only when the agent of the action is not important.
6. Use only the simple present, the simple past and the simple future.
7. Put a condition before the instruction: `If the index is stale, build it again.`
8. Do not use semicolons in sentences. Write two sentences.

### Paragraphs, notes and warnings

1. A paragraph has one topic and a maximum of **6 sentences**. Start with the topic sentence.
2. A warning or a caution starts with a clear command. Then it gives the reason.
3. A note gives information. It does not give an instruction.
4. Use a vertical list for a sequence or a set of conditions. Each item of a numbered procedure is one step.

### Tables, headings and diagrams

1. A table cell can be a short phrase. If a cell has a sentence, the sentence obeys the rules.
2. A heading is a noun phrase (`The cost model`) or an imperative (`Run the demo`).
   Do not start a heading with an `-ing` form.
3. A diagram label is a short phrase. Use the same terms as the text.

### What STE does not change

Code, commands, file names, paths, field names, environment variables, status values, enum values,
product names and URLs stay exactly as they are. They are technical names. Put them in backticks.

## 2. General words to replace

| Do not use | Use |
|---|---|
| utilize, leverage | use |
| in order to | to |
| set up | prepare, install, configure |
| carry out, perform | do |
| make sure, ensure | make sure (allowed), or `check that` |
| a lot of, lots of | many, much |
| e.g., i.e. | for example, that is |
| should (instruction) | must (rule) / imperative (step) |
| might, may (possibility) | can |
| very, really, just, simply, easily | (delete) |
| seamless, robust, powerful, blazing | (delete or give a measured fact) |


## 3. Project vocabulary

This section gives the technical names and the technical verbs of adaptive-legacy-code-complexity-harness. The README uses each term with only this meaning.

### 3.1 Technical names (nouns)

| Term | Meaning | Do not use |
|---|---|---|
| **harness** | This repository: the agents, the skills, the scripts and the contracts together | framework, tool, system (for the whole repository) |
| **stage** | One of the four steps: Inventory, Parser, Complexity, Target-Fit | phase, step (for these four) |
| **agent** | A Markdown persona file in `.claude/agents/` that the AI runtime follows to run one stage | bot, assistant, orchestrator (as a noun for the file) |
| **skill** | A `SKILL.md` folder in `.claude/skills/` that tells what one complexity is and when to use it | plugin, module |
| **analyzer** | The Python file `NN_*.py` in `.claude/complexities/` that calculates one complexity | metric script, implementation (except in the three-layer table) |
| **complexity** | One of the 20 measurements, for example Cyclomatic or Migration | metric (except in a formula name), dimension |
| **Normalized Tree** (or **tree**) | The one language-neutral JSON shape that every analyzer reads | AST, parse tree (for this shape), Style-B tree |
| **unit** | One method, routine or paragraph in the tree | function (for a tree entry), node |
| **type** | One class, interface or enum in the tree `types` list | class (for all kinds) |
| **CFG** | The control-flow graph of one unit, with uppercase `node_type` values | flow tree, AST |
| **decision node** | A CFG node that adds one independent path (`DECISION_NODES` in `_core.py`) | branch point, condition |
| **inventory artifact** | `inventory_artifact.json`, the output of Stage 1 | scan result, manifest |
| **complexity artifact** | `complexity_artifact.json`, the consolidated output of Stage 3 or Stage 4 | final report, result file |
| **report** | One `reports/NN_<id>.json` file, the output of one analyzer | result (for the file) |
| **human report** | `complexity_report.md`, the prose file that Agent 3 writes | summary, narrative |
| **envelope** | The fixed shape of every report (`result()` in `_core.py`) | wrapper, format |
| **SPEC** | The `Spec` object of one analyzer: id, number, tier, inputs, dependencies | manifest, config |
| **tier** | One of the six groups `size`, `structural`, `data`, `coupling`, `hazard`, `composite` | band (for these groups), layer |
| **level** | One of `L1` trivial, `L2` low, `L3` moderate, `L4` high, `L5` severe | grade, rating, risk band |
| **level thresholds** | The four numbers that map a score to a level | bands (except the code parameter `bands`) |
| **confidence** | The 0 to 1 value that tells how sure an analyzer is of its score, with reasons | certainty, quality |
| **coverage** | The number of analyzers that measured, of all analyzers that were discovered | completeness (except the field name) |
| **hotspot** | A unit that two or more independent analyzers put at `L4` or `L5` | problem area, red flag |
| **`insufficient_input`** | The status of an analyzer that did not get its declared inputs | skipped, zero, empty |
| **judge** | `tools/judge.py`, the audit of all analyzers | linter, test suite |
| **check** | One of the 10 judge checks `C1` to `C10` | test (for a judge check) |
| **canary** | `tools/99_canary_complexity.py`, an analyzer with intentional defects | dummy, mock |
| **target language** | The language that a codebase will move to, named in the request | destination platform |
| **descriptor** | One `languages/<id>.json` file that declares the capabilities of a target language | profile, language config |
| **projected tree** | The tree after `project_tree()` applies the descriptor rules | converted tree, translated tree |
| **source pass / target pass** | The run of the 20 analyzers on the source tree / on the projected tree | baseline run, second run |
| **comparison** | The section of the target artifact that puts source and target results side by side | diff, delta report |
| **Style-A tree** | The old recursive `{kind, children[]}` tree shape | legacy tree, old format |

### 3.2 Technical verbs

| Verb | Meaning |
|---|---|
| **scan** | Read the files of a repository at declaration level (Stage 1) |
| **parse** | Read the method bodies and make the Normalized Tree (Stage 2) |
| **discover** | Find the analyzers by their file names and read each `SPEC` |
| **order** | Sort the analyzers by dependency depth, then tier, then number |
| **gate** | Check the declared inputs of an analyzer before it runs |
| **run** | Call the `analyze()` function of an analyzer |
| **consolidate** | Merge all reports into one complexity artifact, with no new score |
| **project** | Change the tree with the rules of one descriptor |
| **strip** | Remove a field from each unit of the projected tree |
| **drop** | Remove a unit or the `types` list from the projected tree |
| **promote** | Move a reviewed descriptor from `_pending/` to `languages/` |
| **audit** | Run the 10 judge checks on each analyzer |
| **bridge** | Convert a Style-A tree into a Normalized Tree with `tools/tree_bridge.py` |
