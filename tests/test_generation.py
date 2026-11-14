"""Testes de integração para a camada de geração, cache, fallback e endpoints."""

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import RunnableLambda

from app.config import settings
from app.db.repository import (
    get_cached_questions,
    init_db,
    normalize_theme_key,
    save_cached_questions,
)
from app.llm.chain import generate_questions_async
from app.llm.factory import clear_model_overrides, set_model_override, set_provider_override
from app.llm.jobs import JobManager, JobStatus, job_manager
from app.llm.validation import GeneratedQuestion, QuestionBatch, RawQuestion
from app.main import app


class FakeStructuredChatModel(BaseChatModel):
    responses: list[QuestionBatch | Exception]

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: None = None,
        **kwargs: str,
    ) -> ChatResult:
        raise NotImplementedError()

    @property
    def _llm_type(self) -> str:
        return "fake-structured"

    def with_structured_output(self, schema: type, **kwargs: str) -> RunnableLambda:
        def _responder(_: list[BaseMessage]) -> QuestionBatch:
            if not self.responses:
                raise RuntimeError("Sem respostas no FakeStructuredChatModel.")
            next_item = self.responses.pop(0)
            if isinstance(next_item, Exception):
                raise next_item
            return next_item

        return RunnableLambda(_responder)


@pytest.fixture
def client() -> TestClient:
    clear_model_overrides()
    job_manager.clear()
    with TestClient(app) as test_client:
        yield test_client
    clear_model_overrides()
    job_manager.clear()


def test_cache_save_and_read(tmp_path: Path) -> None:
    db_file = tmp_path / "test_quiz.db"
    init_db(db_file)

    theme = "  História   do   Brasil  "
    payload = json.dumps([
        {
            "category": "História",
            "prompt": "Quem foi o primeiro imperador do Brasil?",
            "correct": "Dom Pedro I",
            "distractors": ["Dom Pedro II", "Tiradentes", "Deodoro"],
        }
    ])

    save_cached_questions(db_file, theme, "gemini", "gemini-3.8-flash", 1, payload)

    cached_exact = get_cached_questions(
        db_file,
        "história do brasil",
        "gemini",
        "gemini-3.8-flash",
        1,
    )
    assert cached_exact == payload

    cached_unnormalized = get_cached_questions(
        db_file,
        "   HISTÓRIA   DO   BRASIL   ",
        "gemini",
        "gemini-3.8-flash",
        1,
    )
    assert cached_unnormalized == payload


@pytest.mark.asyncio
async def test_generate_uses_cache(tmp_path: Path) -> None:
    db_file = tmp_path / "test_quiz.db"
    init_db(db_file)

    theme = "Astronomia"
    cached_q = GeneratedQuestion(
        category="Astronomia",
        prompt="Qual o planeta mais próximo do Sol?",
        correct="Mercúrio",
        distractors=["Vênus", "Terra", "Marte"],
    )
    payload = json.dumps([cached_q.model_dump()])
    save_cached_questions(db_file, theme, "gemini", settings.gemini_model, 1, payload)

    result = await generate_questions_async(
        theme=theme,
        n=1,
        requested_provider="gemini",
        db_path=db_file,
    )

    assert result.provider == "gemini"
    assert result.fallback is False
    assert len(result.questions) == 1
    assert result.questions[0].prompt == "Qual o planeta mais próximo do Sol?"


@pytest.mark.asyncio
async def test_fallback_when_provider_fails(tmp_path: Path) -> None:
    db_file = tmp_path / "test_quiz.db"
    init_db(db_file)

    result = await generate_questions_async(
        theme="Tema Sem Chave",
        n=2,
        requested_provider="gemini",
        db_path=db_file,
    )

    assert result.provider == "offline"
    assert result.fallback is True
    assert len(result.questions) == 2


@pytest.mark.asyncio
async def test_offline_fallback_reports_provider_error(tmp_path: Path) -> None:
    db_file = tmp_path / "test_quiz.db"
    init_db(db_file)

    result = await generate_questions_async(
        theme="Tema Sem Chave",
        n=1,
        requested_provider="gemini",
        db_path=db_file,
    )

    assert result.provider == "offline"
    assert result.detail is not None
    assert "gemini:" in result.detail
    assert "Chave de API" in result.detail


@pytest.mark.asyncio
async def test_offline_provider_direct() -> None:
    result = await generate_questions_async(
        theme="Biologia",
        n=3,
        requested_provider="offline",
    )

    assert result.provider == "offline"
    assert result.fallback is True
    assert len(result.questions) == 3


@pytest.mark.asyncio
async def test_retry_mechanism(tmp_path: Path) -> None:
    db_file = tmp_path / "test_quiz.db"
    init_db(db_file)

    good_batch = QuestionBatch(
        questions=[
            RawQuestion(
                category="Física",
                prompt="Qual a velocidade aproximada da luz?",
                correct="300.000 km/s",
                distractors=["150.000 km/s", "500.000 km/s", "100.000 km/s"],
            )
        ]
    )

    fake_model = FakeStructuredChatModel(
        responses=[
            RuntimeError("Falha transitória simulada"),
            good_batch,
        ]
    )
    set_model_override(fake_model)

    try:
        result = await generate_questions_async(
            theme="Física",
            n=1,
            requested_provider="gemini",
            db_path=db_file,
        )
        assert result.provider == "gemini"
        assert result.fallback is False
        assert len(result.questions) == 1
        assert result.questions[0].correct == "300.000 km/s"
    finally:
        clear_model_overrides()


@pytest.mark.asyncio
async def test_fallback_to_reserve_real_provider_saves_cache(tmp_path: Path) -> None:
    db_file = tmp_path / "test_quiz.db"
    init_db(db_file)

    failing_gemini = FakeStructuredChatModel(
        responses=[
            RuntimeError("Gemini indisponível"),
            RuntimeError("Gemini retry também falhou"),
        ]
    )

    valid_hf_batch = QuestionBatch(
        questions=[
            RawQuestion(
                category="Biologia",
                prompt="Qual organela é a usina de energia da célula?",
                correct="Mitocôndria",
                distractors=["Ribossomo", "Lisossomo", "Complexo de Golgi"],
            )
        ]
    )
    succeeding_hf = FakeStructuredChatModel(responses=[valid_hf_batch])

    set_provider_override("gemini", failing_gemini)
    set_provider_override("hf", succeeding_hf)

    try:
        result = await generate_questions_async(
            theme="Biologia Celular",
            n=1,
            requested_provider="gemini",
            db_path=db_file,
        )

        assert result.provider == "hf"
        assert result.fallback is True
        assert len(result.questions) == 1
        assert result.questions[0].correct == "Mitocôndria"
        assert result.detail is not None
        assert "hf" in result.detail

        cached_payload = get_cached_questions(
            db_file,
            "biologia celular",
            "hf",
            settings.hf_model,
            1,
        )
        assert cached_payload is not None
        cached_data = json.loads(cached_payload)
        assert cached_data[0]["correct"] == "Mitocôndria"

        offline_result = await generate_questions_async(
            theme="Biologia Celular",
            n=1,
            requested_provider="offline",
            db_path=db_file,
        )
        assert offline_result.provider == "offline"
        assert offline_result.fallback is True

        cached_offline = get_cached_questions(
            db_file,
            "biologia celular",
            "offline",
            "offline",
            1,
        )
        assert cached_offline is None
    finally:
        clear_model_overrides()


def test_job_manager_prune_limits_growth() -> None:
    mgr = JobManager(max_finished=2, ttl_seconds=1800.0)

    j1 = mgr.create_job(theme="Tema 1", provider="gemini")
    j1.status = JobStatus.DONE
    j1.created_at = time.time() - 10.0

    j2 = mgr.create_job(theme="Tema 2", provider="gemini")
    j2.status = JobStatus.DONE
    j2.created_at = time.time() - 5.0

    j3 = mgr.create_job(theme="Tema 3", provider="gemini")
    j3.status = JobStatus.DONE
    j3.created_at = time.time() - 1.0

    j_pending = mgr.create_job(theme="Tema Pendente", provider="gemini")

    mgr.prune()

    assert mgr.get_job(j1.job_id) is None
    assert mgr.get_job(j2.job_id) is not None
    assert mgr.get_job(j3.job_id) is not None
    assert mgr.get_job(j_pending.job_id) is not None


def test_job_manager_prune_by_ttl() -> None:
    mgr = JobManager(max_finished=10, ttl_seconds=5.0)

    j_old = mgr.create_job(theme="Antigo", provider="gemini")
    j_old.status = JobStatus.DONE
    j_old.created_at = time.time() - 20.0

    j_recent = mgr.create_job(theme="Recente", provider="gemini")
    j_recent.status = JobStatus.DONE
    j_recent.created_at = time.time()

    mgr.prune()

    assert mgr.get_job(j_old.job_id) is None
    assert mgr.get_job(j_recent.job_id) is not None


def test_generate_endpoint_flow(client: TestClient) -> None:
    batch = QuestionBatch(
        questions=[
            RawQuestion(
                category="Química",
                prompt="Qual é o elemento químico com símbolo Na?",
                correct="Sódio",
                distractors=["Potássio", "Nitrogênio", "Níquel"],
            ),
            RawQuestion(
                category="Química",
                prompt="Qual gás é essencial para a respiração humana?",
                correct="Oxigênio",
                distractors=["Gás carbônico", "Metano", "Hélio"],
            ),
        ]
    )
    fake_model = FakeStructuredChatModel(responses=[batch])
    set_model_override(fake_model)

    try:
        post_response = client.post(
            "/api/generate",
            json={"tema": "Química Geral", "n": 2, "provider": "gemini"},
        )
        assert post_response.status_code == 202
        post_data = post_response.json()
        assert "job_id" in post_data
        assert post_data["status"] == "pending"

        job_id = post_data["job_id"]

        final_data = None
        for _ in range(50):
            get_response = client.get(f"/api/generate/{job_id}")
            assert get_response.status_code == 200
            data = get_response.json()
            if data["status"] != "pending":
                final_data = data
                break
            time.sleep(0.05)

        assert final_data is not None
        assert final_data["status"] == "done"
        assert final_data["theme"] == "Química Geral"
        assert final_data["provider"] == "gemini"
        assert final_data["fallback"] is False
        assert len(final_data["questions"]) == 2
        assert final_data["detail"] is None
    finally:
        clear_model_overrides()


def test_generate_endpoint_invalid_tema(client: TestClient) -> None:
    assert client.post("/api/generate", json={"tema": "", "n": 5}).status_code == 400
    assert client.post("/api/generate", json={"tema": "   ", "n": 5}).status_code == 400
    assert client.post("/api/generate", json={"tema": "x" * 121, "n": 5}).status_code == 400
    assert client.post("/api/generate", json={"tema": "Válido", "n": 0}).status_code == 400
    assert client.post("/api/generate", json={"tema": "Válido", "n": 21}).status_code == 400


def test_generate_endpoint_not_found(client: TestClient) -> None:
    response = client.get("/api/generate/job-inexistente-12345")
    assert response.status_code == 404
