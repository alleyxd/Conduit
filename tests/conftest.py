import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pytest_sessionstart(session):
    # the shop database is generated, not committed
    if not (ROOT / "examples" / "shop.db").exists():
        subprocess.run([sys.executable, str(ROOT / "examples" / "make_data.py")], check=True)
