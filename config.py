"""Central config. Set DATABASE_URL to use PostgreSQL, e.g.
   postgresql+psycopg2://user:password@localhost:5432/forging_qms
Default is a local SQLite file so the project runs with zero setup."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
REPORTS_DIR = BASE_DIR / "reports"
SQL_DIR = BASE_DIR / "sql"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'forging_qms.db'}")
