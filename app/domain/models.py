"""Modelos de domínio do quiz."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


class Mode(str, Enum):
    """Modo de operação da partida."""

    SESSION = "session"


class AnswerMode(str, Enum):
    """Como as equipes respondem cada pergunta."""

    SIMULTANEOUS = "simultaneous"


class Phase(str, Enum):
    LOBBY = "lobby"
    QUESTION = "question"
    REVEAL = "reveal"
    FINISHED = "finished"


class Difficulty(str, Enum):
    """Nível de dificuldade da pergunta."""

    FACIL = "facil"
    MEDIO = "medio"
    DIFICIL = "dificil"


DIFFICULTY_WEIGHTS: dict[Difficulty, int] = {
    Difficulty.FACIL: 1,
    Difficulty.MEDIO: 2,
    Difficulty.DIFICIL: 3,
}

WEIGHT_TO_DIFFICULTY: dict[int, Difficulty] = {
    1: Difficulty.FACIL,
    2: Difficulty.MEDIO,
    3: Difficulty.DIFICIL,
}

_DIFFICULTY_ALIASES: dict[str, Difficulty] = {
    "facil": Difficulty.FACIL,
    "fácil": Difficulty.FACIL,
    "medio": Difficulty.MEDIO,
    "médio": Difficulty.MEDIO,
    "dificil": Difficulty.DIFICIL,
    "difícil": Difficulty.DIFICIL,
}


def resolve_difficulty_and_weight(
    difficulty: str | Difficulty | None = None,
    weight: int | None = None,
) -> tuple[Difficulty, int]:
    """Normaliza dificuldade e peso (1=facil, 2=medio, 3=dificil)."""
    resolved_diff: Difficulty | None = None
    if isinstance(difficulty, Difficulty):
        resolved_diff = difficulty
    elif isinstance(difficulty, str) and difficulty.strip():
        resolved_diff = _DIFFICULTY_ALIASES.get(difficulty.strip().casefold())

    if resolved_diff is not None:
        return resolved_diff, DIFFICULTY_WEIGHTS[resolved_diff]

    if isinstance(weight, int) and weight in WEIGHT_TO_DIFFICULTY:
        resolved_diff = WEIGHT_TO_DIFFICULTY[weight]
        return resolved_diff, weight

    return Difficulty.FACIL, 1


class Option(BaseModel):
    id: str
    text: str


class Question(BaseModel):
    """Pergunta pronta para a partida, com opções já embaralhadas."""

    id: str
    category: str
    prompt: str
    options: list[Option]
    correct_option_id: str
    difficulty: Difficulty = Difficulty.FACIL
    weight: int = 1


class PlayerSummary(BaseModel):
    id: str
    nickname: str


class Player(BaseModel):
    id: str
    token: str
    nickname: str
    team_id: str


class Team(BaseModel):
    id: str
    name: str
    score: int = 0
    answered: bool = False
    players: list[PlayerSummary] = Field(default_factory=list)


class AnswerRecord(BaseModel):
    team_id: str
    option_id: str
    correct: bool
    points: int
    elapsed: float
    player_id: str | None = None


class TeamResult(BaseModel):
    id: str
    name: str
    score: int


DistractorStr = Annotated[str, Field(min_length=1, max_length=40)]


class GeneratedQuestionInput(BaseModel):
    category: str = Field(default="", max_length=50)
    prompt: str = Field(min_length=1, max_length=200)
    correct: str = Field(min_length=1, max_length=40)
    distractors: list[DistractorStr] = Field(min_length=3, max_length=3)
    difficulty: Difficulty = Difficulty.FACIL
    weight: int = Field(default=1, ge=1, le=3)


class Room:
    """Estado de uma partida. Mutado apenas pelo GameEngine."""

    def __init__(
        self,
        *,
        code: str,
        host_token: str,
        mode: Mode,
        answer_mode: AnswerMode,
        teams: list[Team],
        questions: list[Question],
        theme: str,
        provider: str,
        question_time: int,
    ) -> None:
        self.code = code
        self.host_token = host_token
        self.mode = mode
        self.answer_mode = answer_mode
        self.teams = teams
        self.questions = questions
        self.theme = theme
        self.provider = provider
        self.question_time = question_time

        self.index = 0
        self.phase = Phase.LOBBY
        self.deadline = 0.0
        self.answers: list[AnswerRecord] = []
        self.all_answers: list[AnswerRecord] = []
        self.created_at = datetime.now()
        self.finished_at: datetime | None = None
        self.persisted = False
        self.players_by_token: dict[str, Player] = {}
        self.players_by_id: dict[str, Player] = {}

    @property
    def current(self) -> Question:
        return self.questions[self.index]

    def team(self, team_id: str) -> Team | None:
        return next((t for t in self.teams if t.id == team_id), None)


class CreateRoomRequest(BaseModel):
    mode: Mode = Mode.SESSION
    team_names: list[str] = Field(
        default_factory=lambda: ["Equipe 1", "Equipe 2"],
        min_length=2,
        max_length=2,
    )
    theme_id: str = ""
    n: int = Field(default=10, ge=1, le=20)
    generated_questions: list[GeneratedQuestionInput] | None = Field(
        default=None, max_length=20
    )


class JoinTeamInfo(BaseModel):
    id: str
    name: str
    members: int
    capacity: int


class JoinInfoResponse(BaseModel):
    code: str
    mode: str
    phase: str
    theme: str
    teams: list[JoinTeamInfo]


class PlayerJoinRequest(BaseModel):
    nickname: str
    team_id: str


class PlayerJoinResponse(BaseModel):
    player_id: str
    player_token: str
    team_id: str
    team_name: str
