"""Testes unitários para a validação estrita de perguntas."""

from pathlib import Path

from app.llm.validation import (
    RawQuestion,
    load_bank_prompts,
    normalize_text,
    validate_batch,
    validate_single_question,
)


def test_normalize_text() -> None:
    assert normalize_text("  Pergunta   com   Espaços  ") == "pergunta com espaços"


def test_validate_single_question_valid() -> None:
    seen_prompts: set[str] = set()
    bank_prompts: set[str] = set()
    raw = RawQuestion(
        category="História",
        prompt="Quem proclamou a República no Brasil?",
        correct="Marechal Deodoro",
        distractors=["Dom Pedro II", "Tiradentes", "Getúlio Vargas"],
    )
    result = validate_single_question(raw, "História", seen_prompts, bank_prompts)
    assert result is not None
    assert result.prompt == "Quem proclamou a República no Brasil?"
    assert result.correct == "Marechal Deodoro"
    assert len(result.distractors) == 3
    assert result.category == "História"
    assert "quem proclamou a república no brasil?" in seen_prompts


def test_reject_prompt_too_long() -> None:
    seen_prompts: set[str] = set()
    bank_prompts: set[str] = set()
    raw = RawQuestion(
        category="Teste",
        prompt="A" * 201,
        correct="Correta",
        distractors=["E1", "E2", "E3"],
    )
    assert validate_single_question(raw, "Teste", seen_prompts, bank_prompts) is None


def test_reject_empty_prompt() -> None:
    seen_prompts: set[str] = set()
    bank_prompts: set[str] = set()
    raw = RawQuestion(
        category="Teste",
        prompt="   ",
        correct="Correta",
        distractors=["E1", "E2", "E3"],
    )
    assert validate_single_question(raw, "Teste", seen_prompts, bank_prompts) is None


def test_reject_correct_too_long() -> None:
    seen_prompts: set[str] = set()
    bank_prompts: set[str] = set()
    raw = RawQuestion(
        category="Teste",
        prompt="Pergunta curta?",
        correct="C" * 41,
        distractors=["E1", "E2", "E3"],
    )
    assert validate_single_question(raw, "Teste", seen_prompts, bank_prompts) is None


def test_reject_distractor_too_long() -> None:
    seen_prompts: set[str] = set()
    bank_prompts: set[str] = set()
    raw = RawQuestion(
        category="Teste",
        prompt="Pergunta curta?",
        correct="Correta",
        distractors=["E1", "D" * 41, "E3"],
    )
    assert validate_single_question(raw, "Teste", seen_prompts, bank_prompts) is None


def test_reject_missing_distractor() -> None:
    seen_prompts: set[str] = set()
    bank_prompts: set[str] = set()
    raw = RawQuestion(
        category="Teste",
        prompt="Pergunta?",
        correct="Correta",
        distractors=["E1", "E2"],
    )
    assert validate_single_question(raw, "Teste", seen_prompts, bank_prompts) is None


def test_reject_duplicate_options_among_distractors() -> None:
    seen_prompts: set[str] = set()
    bank_prompts: set[str] = set()
    raw = RawQuestion(
        category="Teste",
        prompt="Pergunta?",
        correct="Correta",
        distractors=["Erro", "erro ", "Outro"],
    )
    assert validate_single_question(raw, "Teste", seen_prompts, bank_prompts) is None


def test_reject_option_equal_to_correct() -> None:
    seen_prompts: set[str] = set()
    bank_prompts: set[str] = set()
    raw = RawQuestion(
        category="Teste",
        prompt="Pergunta?",
        correct="Correta",
        distractors=["correta", "Erro 1", "Erro 2"],
    )
    assert validate_single_question(raw, "Teste", seen_prompts, bank_prompts) is None


def test_reject_duplicate_prompt_in_batch() -> None:
    bank_prompts: set[str] = set()
    raw1 = RawQuestion(
        category="Teste",
        prompt="Qual a capital do Brasil?",
        correct="Brasília",
        distractors=["Rio de Janeiro", "São Paulo", "Salvador"],
    )
    raw2 = RawQuestion(
        category="Teste",
        prompt="  qual a capital do brasil?  ",
        correct="Brasília",
        distractors=["Curitiba", "Belo Horizonte", "Recife"],
    )
    batch = validate_batch([raw1, raw2], "Geografia", 5, bank_prompts)
    assert len(batch) == 1
    assert batch[0].prompt == "Qual a capital do Brasil?"


def test_reject_duplicate_prompt_in_bank(tmp_path: Path) -> None:
    bank_file = tmp_path / "perguntas.json"
    bank_file.write_text(
        '[{"prompt": "Qual é a capital de Minas Gerais?", "correct": "BH", "distractors": ["SP", "RJ", "ES"]}]',
        encoding="utf-8",
    )
    bank_prompts = load_bank_prompts(bank_file)
    assert "qual é a capital de minas gerais?" in bank_prompts

    raw = RawQuestion(
        category="Geografia",
        prompt="Qual é a capital de Minas Gerais?",
        correct="Belo Horizonte",
        distractors=["Contagem", "Betim", "Uberlândia"],
    )
    seen_prompts: set[str] = set()
    assert validate_single_question(raw, "Geografia", seen_prompts, bank_prompts) is None


def test_validate_batch_limits_to_n() -> None:
    raw_list = [
        RawQuestion(
            category="",
            prompt=f"Pergunta número {i}?",
            correct=f"Certa {i}",
            distractors=[f"E1 {i}", f"E2 {i}", f"E3 {i}"],
        )
        for i in range(10)
    ]
    batch = validate_batch(raw_list, "Matemática", 3, set())
    assert len(batch) == 3
    assert all(q.category == "Matemática" for q in batch)
