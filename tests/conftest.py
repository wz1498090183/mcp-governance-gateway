# -*- coding: utf-8 -*-
"""pytest 配置：确保 src 与 tests 可导入（未安装包时兜底）。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT / "src", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
