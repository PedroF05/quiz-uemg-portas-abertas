"""Configuração da aplicação, carregada de variáveis de ambiente / .env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    public_url: str = ""

    data_dir: Path = BASE_DIR / "data"
    db_path: Path = BASE_DIR / "data" / "quiz.db"

    question_time: int = 20
    base_points: int = 10
    speed_bonus: int = 5
    max_team_size: int = 3

    llm_provider: str = "offline"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    hf_token: str = ""
    hf_model: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b-instruct"
    ollama_timeout: int = 180
    ollama_num_ctx: int = 4096
    ollama_think: bool = False

    @property
    def themes_dir(self) -> Path:
        return self.data_dir / "temas"

    @property
    def bank_path(self) -> Path:
        return self.data_dir / "perguntas.json"


settings = Settings()
