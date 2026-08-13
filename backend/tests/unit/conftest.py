"""Environment for the unit suite.

These tests import `server` directly and exercise pure functions only. Motor
connects lazily, so no MongoDB is needed — which is the point: the rest of the
suite needs a running preview backend and can't gate a pull request.
"""
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "wearecreators_unit")
os.environ.setdefault("JWT_SECRET", "unit-test-secret")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
