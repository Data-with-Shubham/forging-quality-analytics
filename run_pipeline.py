"""One-command run: generate sample data -> validate/load -> export KPIs."""
import subprocess, sys
from pathlib import Path

src = Path(__file__).parent / "src"
for script in ["generate_data.py", "etl.py", "kpis.py"]:
    print(f"\n>>> Running {script}")
    subprocess.run([sys.executable, script], cwd=src, check=True)
print("\nDone. Open /reports/*.csv in Power BI, or query forging_qms.db with sql/kpi_queries.sql")
