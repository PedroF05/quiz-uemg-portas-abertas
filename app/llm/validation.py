"""Validação de perguntas geradas por LLM."""

import json
from pathlib import Path

from pydantic import BaseModel, Field


class RawQuestion(BaseModel):
    category: str = ""
    prompt: str
    correct: str
    distractors: list[str] = Field(default_factory=list)


class QuestionBatch(BaseModel):
    questions: list[RawQuestion] = Field(default_factory=list)


class GeneratedQuestion(BaseModel):
    category: str
    prompt: str
    correct: str
    distractors: list[str]


class ValidationError(Exception):
    """Exceção levantada quando nenhuma pergunta válida é gerada."""

    pass


def normalize_text(text: str) -> str:
    """Normaliza texto colapsando espaços em branco e convertendo para minúsculas."""
    return " ".join(text.strip().lower().split())


def load_bank_prompts(bank_path: Path) -> set[str]:
    """Carrega enunciados normalizados do banco existente para evitar duplicações."""
    if not bank_path.exists():
        return set()
    with bank_path.open(encoding="utf-8") as handle:
        data: list[dict[str, str | list[str]]] = json.load(handle)
    prompts: set[str] = set()
    for item in data:
        if isinstance(item, dict) and "prompt" in item:
            prompts.add(normalize_text(str(item["prompt"])))
    return prompts


def validate_single_question(
    question: RawQuestion,
    theme: str,
    seen_prompts: set[str],
    bank_prompts: set[str],
) -> GeneratedQuestion | None:
    """Valida uma única pergunta contra as regras de tamanho, unicidade e opções."""
    prompt = question.prompt.strip()
    if not prompt or len(prompt) > 200:
        return None

    normalized_prompt = normalize_text(prompt)
    if normalized_prompt in seen_prompts or normalized_prompt in bank_prompts:
        return None

    correct = question.correct.strip()
    if not correct or len(correct) > 40:
        return None

    if len(question.distractors) != 3:
        return None

    trimmed_distractors = [d.strip() for d in question.distractors]
    if any(not d or len(d) > 40 for d in trimmed_distractors):
        return None

    all_options = {correct.casefold(), *(d.casefold() for d in trimmed_distractors)}
    if len(all_options) != 4:
        return None

    category = question.category.strip() or theme.strip() or "Geral"

    seen_prompts.add(normalized_prompt)
    return GeneratedQuestion(
        category=category,
        prompt=prompt,
        correct=correct,
        distractors=trimmed_distractors,
    )


def validate_batch(
    raw_questions: list[RawQuestion],
    theme: str,
    n: int,
    bank_prompts: set[str],
) -> list[GeneratedQuestion]:
    """Filtra perguntas válidas, descartando inválidas até o limite de n."""
    seen_prompts: set[str] = set()
    valid_questions: list[GeneratedQuestion] = []
    for raw in raw_questions:
        validated = validate_single_question(raw, theme, seen_prompts, bank_prompts)
        if validated is not None:
            valid_questions.append(validated)
            if len(valid_questions) == n:
                break
    return valid_questions
