from types import SimpleNamespace

import pytest

from app.domain.models import (
    AnswerMode,
    Mode,
    Option,
    PlayerSummary,
    Question,
    Room,
    Team,
)
from app.game.engine import EngineError, GameEngine


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_question(question_id: str = "q1") -> Question:
    return Question(
        id=question_id,
        category="Teste",
        prompt="Pergunta?",
        options=[
            Option(id="o1", text="Certa"),
            Option(id="o2", text="Errada 1"),
            Option(id="o3", text="Errada 2"),
            Option(id="o4", text="Errada 3"),
        ],
        correct_option_id="o1",
    )


def make_engine(questions: int = 2) -> tuple[GameEngine, FakeClock]:
    teams = [
        Team(
            id="t1",
            name="Um",
            players=[PlayerSummary(id="p1", nickname="Alice")],
        ),
        Team(
            id="t2",
            name="Dois",
            players=[PlayerSummary(id="p2", nickname="Bob")],
        ),
    ]
    room = Room(
        code="ABC123",
        host_token="token",
        mode=Mode.SESSION,
        answer_mode=AnswerMode.SIMULTANEOUS,
        teams=teams,
        questions=[make_question(f"q{i}") for i in range(1, questions + 1)],
        theme="Teste",
        provider="offline",
        question_time=20,
    )
    clock = FakeClock()
    settings = SimpleNamespace(base_points=10, speed_bonus=5)
    engine = GameEngine(room, settings, clock=clock)
    engine.start_game()
    return engine, clock


def test_correct_answer_in_first_half_scores_bonus():
    engine, clock = make_engine()
    clock.advance(2)
    state = engine.answer("t1", "o1")

    assert state["phase"] == "question"
    assert state["teams"][0]["score"] == 15

    state = engine.answer("t2", "o2")
    assert state["phase"] == "reveal"
    assert state["reveal"]["answers"][0]["points"] == 15


def test_correct_answer_in_second_half_scores_base():
    engine, clock = make_engine()
    clock.advance(12)
    engine.answer("t1", "o1")

    assert engine.room.teams[0].score == 10


def test_wrong_answer_scores_zero():
    engine, _ = make_engine()
    engine.answer("t1", "o2")

    assert engine.room.teams[0].score == 0
    assert engine.room.answers[0].correct is False


def test_answer_after_deadline_is_rejected():
    engine, clock = make_engine()
    clock.advance(21)

    with pytest.raises(EngineError):
        engine.answer("t1", "o1")
    assert engine.room.phase.value == "reveal"


def test_simultaneous_mode_waits_for_both_teams():
    engine, _ = make_engine()

    state = engine.answer("t1", "o1")
    assert state["phase"] == "question"

    state = engine.answer("t2", "o2")
    assert state["phase"] == "reveal"
    assert engine.room.teams[0].score == 15
    assert engine.room.teams[1].score == 0


def test_same_team_cannot_answer_twice():
    engine, _ = make_engine()
    engine.answer("t1", "o1")

    with pytest.raises(EngineError):
        engine.answer("t1", "o2")


def test_advances_to_next_question_and_finishes():
    engine, _ = make_engine()

    engine.answer("t1", "o1")
    engine.answer("t2", "o2")
    state = engine.next_question()

    assert state["index"] == 1
    assert state["phase"] == "question"
    assert all(team["answered"] is False for team in state["teams"])

    engine.answer("t1", "o1")
    engine.answer("t2", "o2")
    state = engine.next_question()

    assert state["phase"] == "finished"
    assert state["winners"] == ["Um"]


def test_snapshot_hides_correct_option_while_question_is_open():
    engine, _ = make_engine()
    state = engine.snapshot()

    assert state["phase"] == "question"
    assert state["reveal"] is None
    assert "turn_team_id" not in state
    assert "correct_option_id" not in state["question"]
    assert len(state["question"]["options"]) == 4


def test_weighted_questions_and_balanced_selection():
    from app.config import settings
    from app.quiz.bank import build_questions

    questions, _ = build_questions(settings, "jogos", 6)
    assert len(questions) == 6
    assert [q.difficulty.value for q in questions] == [
        "facil",
        "facil",
        "medio",
        "medio",
        "dificil",
        "dificil",
    ]
    assert [q.weight for q in questions] == [1, 1, 2, 2, 3, 3]
