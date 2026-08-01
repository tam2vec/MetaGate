# Evidence Model

Each evidence item has:

- `kind`: ownership, glossary, lineage, assertions, incidents, freshness, usage, or policy.
- `present`: whether the signal exists.
- `complete`: whether the signal is complete enough for certification.
- `stale`: whether the signal is older than policy permits.
- `contradictory`: whether sources conflict.
- `confidence`: source confidence from 0.0 to 1.0.
- `details`: original source fields for explainability.

Gap classification:

- `missing`: required evidence is absent.
- `stale`: evidence exists but exceeds policy freshness.
- `incomplete`: evidence exists but lacks required fields.
- `contradictory`: evidence conflicts with another source.
