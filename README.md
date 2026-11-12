# Quiz UEMG de Portas Abertas

Quiz de perguntas e respostas para o evento de portas abertas da UEMG.
Duas equipes de até 3 pessoas, perguntas de temas prontos ou geradas por IA.

O servidor é a fonte de verdade da partida: relógio, pontuação e gabarito ficam nele.

## Rodando

Requisitos: Python 3.11+ e [uv](https://docs.astral.sh/uv/).

```bash
./run.sh          # Linux/macOS
run.bat           # Windows
```

Ou manualmente:

```bash
uv sync
cp .env.example .env
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Abra <http://localhost:8000>. O modo local funciona sem internet e sem chave de API.

## Como jogar

1. Dê nome às duas equipes e escolha o tema e o número de perguntas.
2. "Começar" sorteia as perguntas (no modo local, do banco offline).
3. A equipe da vez responde a pergunta; acertou = 10 pontos, +5 se responder na
   primeira metade dos 20 segundos.
4. Teclas `1`–`4` respondem, `Espaço` avança, `F` alterna tela cheia.
5. O ranking fica no SQLite do servidor (`data/quiz.db`).

## Modos

| Modo | Status | Como funciona |
|---|---|---|
| Local | pronto | Um notebook/projetor; o host clica na resposta |
| Offline | pronto | `LLM_PROVIDER=offline`: nenhuma chamada externa |
| Celular (QR) | fase 3 | Cada jogador responde pelo celular, tipo Kahoot |

## Configuração

Copie `.env.example` para `.env`. As variáveis principais:

| Variável | Descrição |
|---|---|
| `LLM_PROVIDER` | `offline`, `gemini`, `hf` ou `local` |
| `GEMINI_API_KEY` | chave do Google AI Studio |
| `GEMINI_MODEL` | modelo do Gemini (padrão `gemini-3.8-flash`) |
| `HF_TOKEN` / `HF_MODEL` | Hugging Face Inference Providers (opcional) |
| `OLLAMA_MODEL` | modelo local via Ollama (ex.: `qwen2.5:3b-instruct`) |
| `PUBLIC_URL` | URL usada no QR code (fase 3); vazio = IP da LAN |
| `QUESTION_TIME` | segundos por pergunta (padrão 20) |

O `.env` nunca vai para o Git. A chave fica só no servidor.

## Editando perguntas e temas

O banco curado fica em `data/perguntas.json`:

```json
{
  "category": "Jogos",
  "prompt": "Pergunta?",
  "correct": "Resposta certa",
  "distractors": ["errada 1", "errada 2", "errada 3"]
}
```

Temas em `data/temas/*.json`. Um tema pode filtrar uma categoria do banco:

```json
{ "id": "jogos", "name": "Jogos", "category": "Jogos" }
```

ou trazer as próprias perguntas no campo `questions` (útil para temas gerados por IA).

## Testes

```bash
uv run pytest
```

Os testes não chamam API externa.

## Estrutura

```
app/
  main.py            FastAPI
  config.py          configuração via .env
  api/               rotas HTTP
  domain/            modelos e pontuação
  game/              engine e salas
  quiz/              banco e temas
  db/                SQLite
  static/            host em JS puro (módulos ES)
data/                perguntas, temas e banco SQLite
tests/               pytest
docs/plans/          plano de evolução
```

## Legado

O protótipo original continua em `legacy/` (`index.html`, `perguntas.js` e `server.py`) e
pode ser aberto direto no navegador como plano B, sem servidor. O `legacy/server.py` é o
backend antigo do protótipo e não faz parte da aplicação atual; ele serve apenas os
arquivos de `legacy/`.

## Roadmap

Consulte [`docs/plans/2026-11-11-quiz-uemg-portas-abertas.md`](docs/plans/2026-11-11-quiz-uemg-portas-abertas.md).

- Fase 1: estrutura, motor server-side, modo local — **concluída**
- Fase 2: LangChain (Gemini / HF / local) e fallback offline
- Fase 3: celulares via QR e WebSocket
- Fase 4: polimento e ensaio
