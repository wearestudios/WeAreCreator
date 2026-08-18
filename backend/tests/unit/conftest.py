"""Environment for the unit suite.

These tests import `server` directly and exercise pure functions only. Motor
connects lazily, so no MongoDB is needed — which is the point: the rest of the
suite needs a running preview backend and can't gate a pull request.

The three variables below are the ones `validate_environment()` refuses to
start without, so they have to be set before `server` is imported anywhere.
`APP_ENV` is set for the same reason but the other way round: unset reads as
production, and the suite would then log a warning per run about the admin
account and CORS that no test environment is expected to have.
"""
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "wearecreators_unit")
os.environ.setdefault("JWT_SECRET", "unit-test-secret")
os.environ.setdefault("APP_ENV", "test")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
