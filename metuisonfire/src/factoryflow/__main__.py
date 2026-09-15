"""Makes `python -m factoryflow ...` work without installing a console script."""

from factoryflow.cli import main

raise SystemExit(main())
