"""Regra de pontuação, isolada para ser testável."""


def points_for(
    elapsed_seconds: float,
    time_limit: float,
    base: int = 10,
    bonus: int = 5,
) -> int:
    """10 pontos por acerto + 5 se responder na primeira metade do tempo.

    Resposta correta após o limite não pontua (o engine já rejeita, mas a
    função é defensiva para uso direto).
    """
    if elapsed_seconds > time_limit:
        return 0
    if elapsed_seconds <= time_limit / 2:
        return base + bonus
    return base
