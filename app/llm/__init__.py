"""Módulo de integração com LLMs via LangChain."""

from .chain import (
    GenerationResult,
    generate_questions_async,
    generate_questions_sync,
    get_offline_questions,
)
from .factory import build_chat_model, is_provider_configured
from .jobs import GenerationJob, JobStatus, job_manager
from .validation import GeneratedQuestion, RawQuestion, validate_batch

__all__ = [
    "GeneratedQuestion",
    "GenerationJob",
    "GenerationResult",
    "JobStatus",
    "RawQuestion",
    "build_chat_model",
    "generate_questions_async",
    "generate_questions_sync",
    "get_offline_questions",
    "is_provider_configured",
    "job_manager",
    "validate_batch",
]
