"""Gerenciamento de jobs assíncronos de geração de perguntas."""

import time
import uuid
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from ..config import Settings, settings
from .chain import generate_questions_async
from .validation import GeneratedQuestion


class JobStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    ERROR = "error"


class GenerationJob(BaseModel):
    job_id: str
    status: JobStatus
    theme: str
    provider: str
    fallback: bool
    questions: list[GeneratedQuestion] = Field(default_factory=list)
    detail: str | None = None
    created_at: float = Field(default_factory=time.time)


class JobManager:
    """Armazenamento e execução de jobs de geração em memória com descarte de jobs antigos."""

    def __init__(self, max_finished: int = 50, ttl_seconds: float = 1800.0) -> None:
        self._jobs: dict[str, GenerationJob] = {}
        self.max_finished = max_finished
        self.ttl_seconds = ttl_seconds

    def prune(
        self,
        max_finished: int | None = None,
        ttl_seconds: float | None = None,
    ) -> None:
        """Descarta jobs finalizados por tempo ou por limite de contagem, preservando jobs pendentes."""
        max_limit = self.max_finished if max_finished is None else max_finished
        ttl = self.ttl_seconds if ttl_seconds is None else ttl_seconds
        now = time.time()

        finished_keys = [
            key
            for key, job in self._jobs.items()
            if job.status in (JobStatus.DONE, JobStatus.ERROR)
        ]

        for key in finished_keys:
            job = self._jobs.get(key)
            if job is not None and (now - job.created_at > ttl):
                self._jobs.pop(key, None)

        remaining_finished = [
            (key, self._jobs[key].created_at)
            for key in self._jobs
            if self._jobs[key].status in (JobStatus.DONE, JobStatus.ERROR)
        ]

        if len(remaining_finished) > max_limit:
            remaining_finished.sort(key=lambda item: item[1])
            excess = len(remaining_finished) - max_limit
            for key, _ in remaining_finished[:excess]:
                self._jobs.pop(key, None)

    def create_job(
        self,
        theme: str,
        provider: str,
    ) -> GenerationJob:
        """Cria e armazena um novo job de geração com status pendente."""
        self.prune()
        job_id = uuid.uuid4().hex
        job = GenerationJob(
            job_id=job_id,
            status=JobStatus.PENDING,
            theme=theme,
            provider=provider,
            fallback=False,
            questions=[],
            detail=None,
        )
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> GenerationJob | None:
        """Retorna o job correspondente ao identificador ou None se inexistente."""
        return self._jobs.get(job_id)

    def clear(self) -> None:
        """Limpa o registro de jobs para testes isolados."""
        self._jobs.clear()

    async def execute_job(
        self,
        job_id: str,
        theme: str,
        n: int,
        provider: str,
        settings_obj: Settings | None = None,
        db_path: Path | None = None,
        bank_path: Path | None = None,
    ) -> None:
        """Executa a geração em background e atualiza o estado final do job."""
        job = self.get_job(job_id)
        if job is None:
            return

        try:
            result = await generate_questions_async(
                theme=theme,
                n=n,
                requested_provider=provider,
                settings_obj=settings_obj,
                db_path=db_path,
                bank_path=bank_path,
            )
            job.status = JobStatus.DONE
            job.provider = result.provider
            job.fallback = result.fallback
            job.questions = result.questions
            job.detail = result.detail
        except Exception as exc:
            job.status = JobStatus.ERROR
            job.detail = str(exc)
        finally:
            self.prune()


job_manager = JobManager()
