import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(EXP / "scripts"))
