import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _sub in ("plugin/scripts", "plugin/hooks"):
    _p = str(_ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)
