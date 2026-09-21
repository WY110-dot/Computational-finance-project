"""Unicode-path-safe launcher for output verification."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from quantcf.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["verify", *sys.argv[1:]]))

