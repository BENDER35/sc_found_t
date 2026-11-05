import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from scfoundt.cli import main  # noqa: E402

raise SystemExit(main())
