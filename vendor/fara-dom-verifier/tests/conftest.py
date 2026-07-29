"""Make the Fara source tree importable without an editable install."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# These are deliberately pure-function tests. Avoid importing fara.__init__,
# which eagerly imports optional browser/model runtime dependencies.
if "fara" not in sys.modules:
    fara_package = ModuleType("fara")
    fara_package.__path__ = [str(SRC / "fara")]
    sys.modules["fara"] = fara_package
