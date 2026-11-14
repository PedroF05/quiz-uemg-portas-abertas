import os
import tempfile
from pathlib import Path

# Configuração de teste: banco temporário, sem LLM externa.
_tmp = Path(tempfile.mkdtemp(prefix="quiz-uemg-"))
os.environ["DB_PATH"] = str(_tmp / "quiz.db")
os.environ["LLM_PROVIDER"] = "offline"
os.environ["GEMINI_API_KEY"] = ""
os.environ["HF_TOKEN"] = ""
os.environ["HF_MODEL"] = ""
os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:9"
os.environ["OLLAMA_TIMEOUT"] = "1"
