"""Rotas HTTP para geração de perguntas por LLM em segundo plano."""

import asyncio

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..config import settings
from ..llm.jobs import job_manager
from ..llm.validation import GeneratedQuestion

router = APIRouter(prefix="/api", tags=["generation"])


class GenerateRequest(BaseModel):
    tema: str
    n: int = 10
    provider: str | None = None


class GenerateResponse(BaseModel):
    job_id: str
    status: str


class GenerateJobResponse(BaseModel):
    job_id: str
    status: str
    theme: str
    provider: str
    fallback: bool
    questions: list[GeneratedQuestion]
    detail: str | None = None


@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GenerateResponse,
)
async def start_generation(payload: GenerateRequest) -> GenerateResponse:
    """Inicia um job de geração de perguntas em background e retorna 202."""
    cleaned_tema = payload.tema.strip()
    if not cleaned_tema or len(cleaned_tema) > 120:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tema inválido. Deve ter entre 1 e 120 caracteres.",
        )

    if payload.n < 1 or payload.n > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Número de perguntas deve estar entre 1 e 20.",
        )

    provider = (payload.provider or settings.llm_provider).strip().lower()
    job = job_manager.create_job(
        theme=cleaned_tema,
        provider=provider,
    )

    asyncio.create_task(
        job_manager.execute_job(
            job_id=job.job_id,
            theme=cleaned_tema,
            n=payload.n,
            provider=provider,
        )
    )

    return GenerateResponse(job_id=job.job_id, status=job.status.value)


@router.get(
    "/generate/{job_id}",
    response_model=GenerateJobResponse,
)
def get_generation_status(job_id: str) -> GenerateJobResponse:
    """Consulta o status e o resultado do job de geração."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job de geração não encontrado.",
        )

    return GenerateJobResponse(
        job_id=job.job_id,
        status=job.status.value,
        theme=job.theme,
        provider=job.provider,
        fallback=job.fallback,
        questions=job.questions,
        detail=job.detail,
    )
