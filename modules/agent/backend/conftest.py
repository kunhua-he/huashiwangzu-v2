from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "test-secret")

REPO_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_DIR / "backend"
for path in (REPO_DIR, BACKEND_DIR):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)
