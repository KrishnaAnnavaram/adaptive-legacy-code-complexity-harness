# Staging area for unreviewed target descriptors

A file lands here, not in the parent `languages/` directory, the moment it is
drafted for a target that has no descriptor yet. `target_fit.py` never reads
from this folder — only from `languages/` itself — so a draft sitting here
cannot be used by a real run.

## Lifecycle

1. **Draft.** A new `<language>.json` is written here, following the schema
   in `../schema.md`, marked `"source": "drafted"` and `"reviewed": false`.
2. **Review.** A person checks each field against the language's actual
   documented behavior — not against general impression — and corrects
   anything wrong.
3. **Promote.** Once reviewed, the file is moved up into `languages/` and
   `"reviewed"` is flipped to `true`. Only then can a real run use it.

No file is ever moved out of this folder automatically. Promotion is a
deliberate, human action every time, for every language, with no exception
carved out for languages that happen to already exist elsewhere in this repo.
