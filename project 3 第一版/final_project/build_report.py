"""Unicode-path-safe launcher for rebuilding the final PDF."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from quantcf.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["report", *sys.argv[1:]]))

