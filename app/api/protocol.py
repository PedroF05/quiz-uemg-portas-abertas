"""Modelos Pydantic para o protocolo WebSocket."""

from typing import Literal
from pydantic import BaseModel, Field

from ..game.engine import RoomSnapshotDict


class PlayerInfo(BaseModel):
    id: str
    nickname: str


class TeamSnapshot(BaseModel):
    id: str
    name: str
    score: int
    answered: bool
    players: list[PlayerInfo] = Field(default_factory=list)


class OptionSnapshot(BaseModel):
    id: str
    text: str


class QuestionSnapshot(BaseModel):
    id: str
    category: str
    prompt: str
    options: list[OptionSnapshot]


class AnswerSnapshot(BaseModel):
    team_id: str
    option_id: str
    correct: bool
    points: int
    elapsed: float


class RevealSnapshot(BaseModel):
    correct_option_id: str
    answers: list[AnswerSnapshot]


class RoomSnapshot(BaseModel):
    code: str
    mode: str
    answer_mode: str
    phase: str
    index: int
    total: int
    theme: str
    provider: str
    seconds_left: float
    turn_team_id: str | None
    teams: list[TeamSnapshot]
    question: QuestionSnapshot | None
    reveal: RevealSnapshot | None
    winners: list[str]


class HostStartMessage(BaseModel):
    type: Literal["start"]


class HostNextMessage(BaseModel):
    type: Literal["next"]


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    detail: str


class HostStateMessage(BaseModel):
    type: Literal["state"] = "state"
    code: str
    mode: str
    answer_mode: str
    phase: str
    index: int
    total: int
    theme: str
    provider: str
    seconds_left: float
    turn_team_id: str | None
    teams: list[TeamSnapshot]
    question: QuestionSnapshot | None
    reveal: RevealSnapshot | None
    winners: list[str]
    state: RoomSnapshot | None = None

    @classmethod
    def from_snapshot(cls, snapshot_data: RoomSnapshotDict) -> "HostStateMessage":
        snap = RoomSnapshot.model_validate(snapshot_data)
        data = snap.model_dump()
        return cls(**data, state=snap)


class PlayerAnswerMessage(BaseModel):
    type: Literal["answer"]
    option_id: str


class PlayerQuestionMessage(BaseModel):
    type: Literal["question"] = "question"
    index: int
    total: int
    category: str
    prompt: str
    options: list[OptionSnapshot]
    seconds_left: float


class PlayerTeamLockedMessage(BaseModel):
    type: Literal["team_locked"] = "team_locked"
    team_id: str


class PlayerRevealAnswer(BaseModel):
    team_id: str
    option_id: str
    correct: bool
    points: int


class PlayerTeamScore(BaseModel):
    id: str
    name: str
    score: int


class PlayerRevealMessage(BaseModel):
    type: Literal["reveal"] = "reveal"
    correct_option_id: str
    answers: list[PlayerRevealAnswer]
    teams: list[PlayerTeamScore]


class PlayerFinishedMessage(BaseModel):
    type: Literal["finished"] = "finished"
    winners: list[str]
    teams: list[PlayerTeamScore]


class PlayerLobbyMessage(BaseModel):
    type: Literal["lobby"] = "lobby"
    code: str
    team_id: str
    team_name: str
