"""I dati di esempio (seed_demo.py) si caricano senza errori sul modello attuale."""
import os
import subprocess
import sys
from pathlib import Path


def test_seed_demo_carica_i_dati(tmp_path):
    radice = Path(__file__).resolve().parent.parent
    ambiente = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'demo.db'}",
                "UPLOAD_FOLDER": str(tmp_path / "uploads"), "BACKUP_FOLDER": str(tmp_path / "backup"),
                "SECRET_KEY": "test"}
    esito = subprocess.run([sys.executable, str(radice / "seed_demo.py")], cwd=tmp_path, env=ambiente,
                           capture_output=True, text=True, timeout=120)
    assert esito.returncode == 0, esito.stderr[-2000:]
    assert "Dati demo caricati" in esito.stdout
