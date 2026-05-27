#!/usr/bin/env python3
"""兼容旧命令的 data manager shim。

新代码请使用: python -m scripts.data_manager ...
"""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.data_manager import main


if __name__ == "__main__":
    raise SystemExit(main())
