import os
import tempfile
from pathlib import Path

# Configuração de teste: banco temporário, sem LLM externa.
_tmp = Path(tempfile.mkdtemp(prefix="quiz-uemg-"))
os.environ["DB_PATH"] = str(_tmp / "quiz.db")
os.environ["LLM_PROVIDER"] = "offline"
