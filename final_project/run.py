"""Unicode-path-safe launcher for the complete project pipeline."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from quantcf.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["run", *sys.argv[1:]]))

