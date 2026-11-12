"""Cadeia de geração de perguntas com retry, fallback e cache."""

import asyncio
import concurrent.futures
import json
import random
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..config import Settings, settings
from ..db.repository import get_cached_questions, save_cached_questions
from .factory import (
    build_chat_model,
    get_provider_model_name,
    get_provider_timeout,
    is_provider_configured,
)
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .validation import (
    GeneratedQuestion,
    QuestionBatch,
    RawQuestion,
    ValidationError,
    load_bank_prompts,
    validate_batch,
)


class GenerationResult(BaseModel):
    questions: list[GeneratedQuestion] = Field(default_factory=list)
    provider: str
    fallback: bool
    detail: str | None = None


def get_offline_questions(
    bank_path: Path,
    n: int,
    theme: str = "",
    rng: random.Random | None = None,
) -> GenerationResult:
    """Carrega n perguntas do banco offline local com fallback ativo."""
    if not bank_path.exists():
        return GenerationResult(
            questions=[],
            provider="offline",
            fallback=True,
            detail="Banco de perguntas offline não encontrado.",
        )

    with bank_path.open(encoding="utf-8") as handle:
        data: list[dict[str, str | list[str]]] = json.load(handle)

    questions: list[GeneratedQuestion] = []
    for item in data:
        if isinstance(item, dict):
            prompt = str(item.get("prompt", "")).strip()
            correct = str(item.get("correct", "")).strip()
            raw_distractors = item.get("distractors")
            category = str(item.get("category", "")).strip() or theme.strip() or "Geral"
            if prompt and correct and isinstance(raw_distractors, list) and len(raw_distractors) == 3:
                distractors = [str(d).strip() for d in raw_distractors]
                questions.append(
                    GeneratedQuestion(
                        category=category,
                        prompt=prompt,
                        correct=correct,
                        distractors=distractors,
                    )
                )

    chooser = rng or random.Random()
    k = min(n, len(questions))
    selected = chooser.sample(questions, k=k) if questions else []
    return GenerationResult(
        questions=selected,
        provider="offline",
        fallback=True,
        detail="Perguntas obtidas do banco offline.",
    )


def invoke_model_structured(
    model: BaseChatModel,
    theme: str,
    n: int,
    retry_error: str | None = None,
) -> QuestionBatch:
    """Invoca o modelo com structured output exigindo o modelo Pydantic QuestionBatch."""
    runnable = model.with_structured_output(QuestionBatch)
    system_msg = SystemMessage(content=SYSTEM_PROMPT)
    user_msg = HumanMessage(content=build_user_prompt(theme, n, retry_error))
    output = runnable.invoke([system_msg, user_msg])
    if isinstance(output, QuestionBatch):
        return output
    if isinstance(output, dict):
        return QuestionBatch.model_validate(output)
    raise ValueError("Formato de saída inesperado do modelo estruturado.")


async def try_provider_async(
    provider: str,
    theme: str,
    n: int,
    bank_prompts: set[str],
    settings_obj: Settings,
) -> list[GeneratedQuestion] | None:
    """Tenta gerar perguntas via provedor com 1 retry e timeout estrito."""
    timeout = get_provider_timeout(provider, settings_obj)
    try:
        model = build_chat_model(provider, settings_obj)
    except Exception:
        return None

    def _execute(error_msg: str | None) -> list[GeneratedQuestion]:
        batch = invoke_model_structured(model, theme, n, error_msg)
        valid = validate_batch(batch.questions, theme, n, bank_prompts)
        if not valid:
            raise ValidationError("Nenhuma pergunta válida gerada pelo modelo.")
        return valid

    first_error: str = ""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_execute, None),
            timeout=timeout,
        )
    except Exception as exc:
        first_error = str(exc)

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_execute, f"Tentativa anterior falhou: {first_error}"),
            timeout=timeout,
        )
    except Exception:
        return None


async def generate_questions_async(
    theme: str,
    n: int,
    requested_provider: str | None = None,
    settings_obj: Settings | None = None,
    db_path: Path | None = None,
    bank_path: Path | None = None,
) -> GenerationResult:
    """Executa a cadeia completa de geração com cache, retentativas e fallback ordenado."""
    current_settings = settings_obj or settings
    current_db = db_path or current_settings.db_path
    current_bank = bank_path or current_settings.bank_path
    provider = (requested_provider or current_settings.llm_provider).strip().lower()

    bank_prompts = load_bank_prompts(current_bank)

    if provider == "offline":
        return get_offline_questions(current_bank, n, theme)

    model_name = get_provider_model_name(provider, current_settings)
    cached_payload = get_cached_questions(current_db, theme, provider, model_name, n)
    if cached_payload is not None:
        raw_items: list[dict[str, str | list[str]]] = json.loads(cached_payload)
        cached_questions = [GeneratedQuestion.model_validate(item) for item in raw_items]
        return GenerationResult(
            questions=cached_questions,
            provider=provider,
            fallback=False,
            detail=None,
        )

    valid_questions = await try_provider_async(
        provider,
        theme,
        n,
        bank_prompts,
        current_settings,
    )
    if valid_questions is not None:
        payload = json.dumps([q.model_dump() for q in valid_questions])
        save_cached_questions(current_db, theme, provider, model_name, n, payload)
        return GenerationResult(
            questions=valid_questions,
            provider=provider,
            fallback=False,
            detail=None,
        )

    fallback_order = ["gemini", "hf", "local"]
    candidates = [
        candidate
        for candidate in fallback_order
        if candidate != provider and is_provider_configured(candidate, current_settings)
    ]

    for candidate in candidates:
        candidate_questions = await try_provider_async(
            candidate,
            theme,
            n,
            bank_prompts,
            current_settings,
        )
        if candidate_questions is not None:
            candidate_model = get_provider_model_name(candidate, current_settings)
            payload = json.dumps([q.model_dump() for q in candidate_questions])
            save_cached_questions(current_db, theme, candidate, candidate_model, n, payload)
            operator_detail = (
                f"Provedor solicitado '{provider}' indisponível; "
                f"perguntas geradas pelo provedor reserva '{candidate}'."
            )
            return GenerationResult(
                questions=candidate_questions,
                provider=candidate,
                fallback=True,
                detail=operator_detail,
            )

    offline_result = get_offline_questions(current_bank, n, theme)
    offline_result.detail = (
        f"Provedor '{provider}' e reservas indisponíveis; "
        "utilizando perguntas do banco offline."
    )
    return offline_result


def generate_questions_sync(
    theme: str,
    n: int,
    requested_provider: str | None = None,
    settings_obj: Settings | None = None,
    db_path: Path | None = None,
    bank_path: Path | None = None,
) -> GenerationResult:
    """Executa a cadeia de geração de forma síncrona para scripts de linha de comando."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                asyncio.run,
                generate_questions_async(
                    theme=theme,
                    n=n,
                    requested_provider=requested_provider,
                    settings_obj=settings_obj,
                    db_path=db_path,
                    bank_path=bank_path,
                ),
            )
            return future.result()

    return asyncio.run(
        generate_questions_async(
            theme=theme,
            n=n,
            requested_provider=requested_provider,
            settings_obj=settings_obj,
            db_path=db_path,
            bank_path=bank_path,
        )
    )
