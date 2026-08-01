from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/outputs/predicate-demo-app.html"
OUT = ROOT / "examples/outputs/live-datahub-proof.html"


def main() -> None:
    """Keep the live proof page aligned with the polished review console."""
    OUT.write_text(SOURCE.read_text())
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
