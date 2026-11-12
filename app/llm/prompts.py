"""Prompts do sistema e do usuário para geração de perguntas via LLM."""

SYSTEM_PROMPT = (
    "Você cria perguntas de quiz em português do Brasil para o evento 'UEMG de Portas Abertas' "
    "da Universidade do Estado de Minas Gerais, voltado para estudantes do Ensino Médio.\n\n"
    "Diretrizes:\n"
    "- Use apenas fatos reais, verificáveis e com rigor conceitual.\n"
    "- Conteúdo leve, interessante e adequado para jovens do Ensino Médio.\n"
    "- Varie a dificuldade das perguntas dentro do tema proposto.\n\n"
    "Regras estritas:\n"
    "1. O enunciado ('prompt') deve ter no máximo 200 caracteres e ser direto.\n"
    "2. A resposta correta ('correct') deve ter no máximo 40 caracteres.\n"
    "3. Devem existir exatamente 3 alternativas erradas ('distractors'), plausíveis, "
    "cada uma com no máximo 40 caracteres.\n"
    "4. Todas as 4 alternativas precisam ser distintas entre si.\n"
    "5. O campo 'category' deve indicar o tema da pergunta."
)


def build_user_prompt(theme: str, n: int, retry_error: str | None = None) -> str:
    """Monta o prompt do usuário, incluindo instruções de correção se houver retry."""
    cleaned_theme = theme.strip()[:120]
    if retry_error:
        return (
            f"Tema: {cleaned_theme}.\n"
            f"Crie {n} perguntas de quiz seguindo rigorosamente todas as regras.\n"
            f"Atenção: a tentativa anterior falhou com a seguinte validação:\n{retry_error}\n"
            "Corrija os problemas apontados e retorne apenas perguntas em conformidade."
        )
    return (
        f"Tema: {cleaned_theme}.\n"
        f"Crie {n} perguntas de quiz variando a dificuldade e adequadas ao Ensino Médio."
    )
