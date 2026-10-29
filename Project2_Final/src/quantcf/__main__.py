"""Allow ``python -m quantcf`` when the package is on ``PYTHONPATH``."""

from .cli import main


raise SystemExit(main())

