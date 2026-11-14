"""Script CLI para pré-geração de temas e gravação em data/temas/<slug>.json."""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.llm.chain import generate_questions_sync


def make_slug(value: str) -> str:
    """Gera um slug simples a partir de uma string com acentos e caracteres especiais."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return slug or "tema"


def main() -> None:
    """Ponto de entrada do script CLI."""
    parser = argparse.ArgumentParser(
        description="Gera perguntas para um tema e grava no formato aceito pelo projeto.",
    )
    parser.add_argument(
        "--tema",
        type=str,
        required=True,
        help="Tema das perguntas a serem geradas.",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=10,
        help="Quantidade de perguntas a gerar (1 a 20).",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Provedor a utilizar: gemini, hf, local ou offline.",
    )
    parser.add_argument(
        "--saida",
        type=str,
        default=None,
        help="Caminho do arquivo de saída JSON.",
    )

    args = parser.parse_args()

    if args.n < 1 or args.n > 20:
        print("Erro: --n deve estar entre 1 e 20.", file=sys.stderr)
        sys.exit(2)

    requested_provider = (args.provider or settings.llm_provider).strip().lower()

    result = generate_questions_sync(
        theme=args.tema,
        n=args.n,
        requested_provider=args.provider,
    )

    if result.detail:
        print(f"Detalhe: {result.detail}", file=sys.stderr)

    if not result.questions:
        print("Erro: nenhuma pergunta foi gerada.", file=sys.stderr)
        sys.exit(1)

    if requested_provider != "offline" and result.provider == "offline":
        print(
            f"Erro: o provedor '{requested_provider}' não respondeu e a geração caiu "
            "para o banco offline. Nenhum arquivo foi gravado.",
            file=sys.stderr,
        )
        sys.exit(1)

    slug = make_slug(args.tema)
    if args.saida:
        output_path = Path(args.saida)
    else:
        output_path = settings.themes_dir / f"{slug}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": slug,
        "name": args.tema,
        "questions": [q.model_dump() for q in result.questions],
    }

    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        f"Sucesso: {len(result.questions)} perguntas salvas em {output_path} "
        f"(provedor: {result.provider}, fallback: {result.fallback})",
    )


if __name__ == "__main__":
    main()
