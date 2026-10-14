import os

# Zero-setup default for local runs; Docker Compose and CI point this at PostgreSQL.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///signal_problems.db")
