"""Carregamento do banco de perguntas e dos temas prontos."""

import json
import random
import uuid
from pathlib import Path

from ..config import Settings
from ..domain.models import Option, Question


class BankError(Exception):
    pass


def _read_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _raw_bank(settings: Settings) -> list[dict]:
    if not settings.bank_path.exists():
        raise BankError("Banco de perguntas não encontrado.")
    return _read_json(settings.bank_path)


def _theme_files(settings: Settings) -> list[Path]:
    if not settings.themes_dir.exists():
        return []
    return sorted(settings.themes_dir.glob("*.json"))


def _read_theme(settings: Settings, theme_id: str) -> dict:
    for path in _theme_files(settings):
        data = _read_json(path)
        if data.get("id") == theme_id:
            return data
    raise BankError("Tema não encontrado.")


def theme_questions(settings: Settings, theme_id: str) -> tuple[list[dict], str]:
    """Perguntas de um tema. O tema pode trazer as perguntas ou filtrar o banco."""
    if not theme_id:
        return _raw_bank(settings), "Banco geral"

    data = _read_theme(settings, theme_id)
    if data.get("questions"):
        return data["questions"], data.get("name", theme_id)

    category = data.get("category")
    if category:
        selected = [q for q in _raw_bank(settings) if q.get("category") == category]
        return selected, data.get("name", theme_id)

    raise BankError("Tema sem perguntas.")


def list_themes(settings: Settings) -> list[dict]:
    themes = []
    for path in _theme_files(settings):
        data = _read_json(path)
        theme_id = data.get("id", path.stem)
        try:
            questions, name = theme_questions(settings, theme_id)
        except BankError:
            questions, name = [], data.get("name", theme_id)
        themes.append({"id": theme_id, "name": name, "count": len(questions)})
    return themes


def _is_valid(item: dict) -> bool:
    if not isinstance(item.get("prompt"), str) or not item["prompt"].strip():
        return False
    if not isinstance(item.get("correct"), str) or not item["correct"].strip():
        return False
    distractors = item.get("distractors")
    if not isinstance(distractors, list) or len(distractors) != 3:
        return False
    if not all(isinstance(d, str) and d.strip() for d in distractors):
        return False
    texts = {item["correct"].strip().casefold(), *(d.strip().casefold() for d in distractors)}
    return len(texts) == 4


def build_questions(
    settings: Settings,
    theme_id: str,
    n: int,
    rng: random.Random | None = None,
) -> tuple[list[Question], str]:
    """Sorteia n perguntas do tema e embaralha as opções de cada uma."""
    raw, theme_name = theme_questions(settings, theme_id)
    valid = [item for item in raw if _is_valid(item)]
    if not valid:
        raise BankError("O tema não tem perguntas válidas.")

    rng = rng or random.Random()
    chosen = rng.sample(valid, k=min(n, len(valid)))

    questions: list[Question] = []
    for item in chosen:
        texts = [item["correct"], *item["distractors"]]
        rng.shuffle(texts)
        options = [Option(id=uuid.uuid4().hex, text=text) for text in texts]
        correct = next(o.id for o in options if o.text == item["correct"])
        questions.append(
            Question(
                id=uuid.uuid4().hex,
                category=str(item.get("category", theme_name)),
                prompt=item["prompt"],
                options=options,
                correct_option_id=correct,
            )
        )

    return questions, theme_name
