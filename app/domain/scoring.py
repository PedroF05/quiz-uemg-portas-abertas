"""Regra de pontuação, isolada para ser testável."""


def points_for(
    elapsed_seconds: float,
    time_limit: float,
    base: int = 10,
    bonus: int = 5,
    weight: int = 1,
) -> int:
    """Pontuação base (10 + 5 de velocidade) multiplicada pelo peso (1, 2 ou 3).

    Resposta correta após o limite não pontua (o engine já rejeita, mas a
    função é defensiva para uso direto).
    """
    if elapsed_seconds > time_limit or weight <= 0:
        return 0
    raw = base + bonus if elapsed_seconds <= time_limit / 2 else base
    return raw * weight
