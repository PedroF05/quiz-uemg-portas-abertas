# Plano de evolução — Quiz UEMG de Portas Abertas

> Documento de planejamento com andamento atualizado em 2026-11-12. Fases 1 e 2
> concluídas, Fase 3 com 6 de 8 itens concluídos e Fase 4 parcial. A auditoria item a
> item está em `.scratch/quiz-uemg/implemented/auditoria-plano.md`.
> Destino final no repositório: `docs/plans/` (copiar quando sair do modo plano).

## 1. Contexto

Projeto da turma para o evento "UEMG de Portas Abertas": um quiz de perguntas e respostas
apresentado em um notebook ligado ao projetor. A base foi feita pela turma; a evolução
busca estruturar o protótipo, integrar LangChain para chamadas de LLM, adicionar um
modelo local/Hugging Face e suportar partidas com celulares via QR code.

### Estado atual

| Arquivo | Conteúdo |
|---|---|
| `index.html` | SPA completa: CSS inline, estado global, telas inicio/pergunta/fim, ranking em `localStorage` |
| `perguntas.js` | 25 perguntas fixas em `[categoria, pergunta, certa, [3 erradas]]` |
| `server.py` | stdlib: estáticos + `POST /gerar`; Gemini REST cru com retry; fallback Anthropic |

Pontos fortes: funciona offline, sem dependências, fallback automático para o banco local,
escape de HTML correto, retry de 429/503 já previsto.

Dívidas:
- validação da resposta no cliente (inviabiliza multiplayer);
- estado global e DOM via `innerHTML`;
- `/gerar` síncrono e bloqueante;
- sem `.gitignore`, `pyproject`, testes ou CI;
- banco de perguntas só no cliente;
- timer impreciso (`setInterval` decrementando 0.1).

## 2. Escopo e decisões travadas

| Tema | Decisão |
|---|---|
| Modo local | Passa a ser um modo de operação do servidor, não um HTML aberto por duplo clique |
| Offline | Modo de operação sem chamadas externas, usando temas/perguntas pré-existentes em JSON |
| Frontend | JS puro, módulos ES, sem etapa de build |
| LLM | LangChain; provedores `gemini`, `hf`, `local`, `offline` |
| Anthropic | Removido |
| Modelo local | Ollama, CPU-only (Ryzen 7 5700U, 8 GB) |
| Times | 2 times, até **3 pessoas por time** |
| Ranking | SQLite no servidor |
| Curadoria | Não há. Perguntas são geradas na hora, por tema pronto ou tema livre |
| Entrega | Versão local pronta para rodar + preparada para deploy |

Premissas a confirmar (ver seção 14):
- modo celular é simultâneo (as duas equipes respondem a mesma pergunta);
- qualquer membro do time pode responder, e a primeira resposta do time trava a rodada.

## 3. Arquitetura alvo

Um único serviço FastAPI. O servidor é a única fonte de verdade do jogo:

```
┌────────────────────────────┐
│ host.html (notebook/projetor) │
│ lobby · pergunta · reveal      │
│ placar · QR                    │
└──────────────┬─────────────┘
               │ HTTP + WS (host)
┌──────────────▼──────────────────────────┐
│ FastAPI                                  │
│  ├─ GameEngine (autoritativo)            │
│  │   turnos, timers, pontuação, gabarito │
│  ├─ RoomManager (1 sala ativa)           │
│  ├─ LLM factory + cache                  │
│  └─ repositório SQLite (ranking/histórico)│
└──────────────┬──────────────────────────┘
               │ WS (jogador)
┌──────────────▼─────────────┐
│ play.html (celular via QR)  │
│ entrar no time · responder  │
└─────────────────────────────┘
```

Princípios:
1. **Um motor só.** Modo local e modo celular usam a mesma máquina de estados; muda
   apenas quem envia as respostas.
2. **Gabarito nunca sai do servidor** antes do reveal.
3. **Relógio no servidor**; o cliente apenas anima a barra a partir do `deadline`.
4. **Nenhuma chamada de LLM durante a partida.** Geração acontece no lobby.
5. **Degradação graciosa:** qualquer falha de LLM cai para tema pronto/offline.

## 4. Regras do jogo

- 2 equipes, até 3 membros cada (host define nomes; membros entram pelo celular).
- 6, 10 ou 14 perguntas por partida (mantém o seletor atual).
- 20 s por pergunta.
- Pontuação: 10 pontos por acerto + 5 se responder na primeira metade (10 s).
- `answer_mode`:
  - `alternate` (modo local): o time da vez responde; acerto pontua só ele.
  - `simultaneous` (modo celular): as duas equipes respondem a mesma pergunta; ambas
    podem pontuar.
- Tempo esgotado = 0 ponto, com reveal automático.
- Empate: mostrar empate (comportamento atual).

### Resposta por time (modo celular)

Cada membro tem seu próprio dispositivo e escolhe o time no ingresso. A resposta é
registrada **por time**: a primeira resposta válida de qualquer membro trava a rodada
para aquele time. Os demais dispositivos mostram "Sua equipe já respondeu". Vantagem:
não exige consenso nem sincronização entre celulares, e 3 pessoas podem jogar com 1
celular cada.

## 5. Backend

### Stack

- FastAPI + Uvicorn
- Pydantic v2 + pydantic-settings (`.env`)
- LangChain (ver seção 6)
- `qrcode[pil]` para gerar o QR no servidor
- `sqlite3` da stdlib com repositório explícito (sem ORM) — só 3–4 tabelas
- pytest + pytest-asyncio

### Endpoints HTTP

| Método | Rota | Função |
|---|---|---|
| GET | `/` | host (lobby/projetor) |
| GET | `/play?room=CODE` | tela do jogador |
| GET | `/api/themes` | temas prontos disponíveis |
| POST | `/api/rooms` | cria sala; devolve código, token do host, URL/QR |
| GET | `/api/rooms/{code}/qr.png` | QR com `PUBLIC_URL` ou IP da LAN |
| POST | `/api/rooms/{code}/prepare` | inicia geração em background (tema pronto ou livre) |
| GET | `/api/rooms/{code}/state` | estado atual (fallback de reconexão) |
| GET | `/api/health` | DB, provider configurado, alcance do modelo |
| GET | `/api/ranking` | ranking persistido |

### WebSocket

- `/ws/host/{code}?token=...`
- `/ws/player/{code}?token=...`

Mensagens JSON com `type` validado por Pydantic (protocolo versionado em
`app/api/protocol.py`).

Cliente → servidor:
`join`, `answer {question_id, option_id}`, `heartbeat`, `rejoin`;
host: `start`, `next`, `reveal`, `end`, `kick`.

Servidor → cliente:
`room_state`, `player_joined`, `player_left`, `generation_status`,
`question {id, index, total, category, prompt, options[], deadline_ms}`,
`answer_ack`, `team_locked`, `reveal {correct_option_id, per_team}`,
`scoreboard`, `game_over`, `error`.

Detalhes:
- timer por pergunta via `asyncio.create_task` com `deadline` monotônico;
- resposta após o deadline recebe `answer_ack {accepted: false, reason: "late"}`;
- reconexão: `player_token` em `localStorage`; servidor reenvia `room_state` e a
  pergunta atual com o tempo restante;
- opções embaralhadas no servidor, com `option_id` estável; o cliente responde por id,
  nunca por índice/letra (evita cópia entre celulares e ambiguidade de ordem);
- host tem token próprio, gerado na criação da sala.

### Geração em background

1. Host escolhe tema pronto **ou** digita tema livre.
2. `POST /prepare` cria um job em memória e responde imediatamente.
3. O job chama a cadeia LangChain com timeout do provider; o status vai por WS
   (`generation_status`: `pending|ok|fallback|error`).
4. "Começar" fica habilitado quando a fila está pronta. Se o job falhar, o host pode
   iniciar com o banco offline (a UI avisa).
5. Nada disso bloqueia a partida em andamento — a geração só existe no lobby.

## 6. Camada LLM (LangChain)

### Factory

`app/llm/factory.py` lê `LLM_PROVIDER` (`gemini|hf|local|offline`) e devolve um
`BaseChatModel`. Trocam-se apenas os imports/classes:

- `gemini` → `ChatGoogleGenerativeAI` (`langchain-google-genai`)
- `hf` → `HuggingFaceEndpoint`/`ChatHuggingFace` (`langchain-huggingface`) **ou** o router
  compatível com OpenAI (`https://router.huggingface.co/v1`) via `ChatOpenAI`
- `local` → `ChatOllama` (`langchain-ollama`)
- `offline` → não usa LLM; lê `data/perguntas.json` / `data/temas/*.json`

### Cadeia

```
tema, n
  → prompt de sistema (evoluir o SISTEMA atual)
  → ChatModel
  → with_structured_output(list[PerguntaGerada])
  → validação de regras
  → cache SQLite
  → fallback (outro provider → banco offline)
```

### Validação obrigatória

- `q` não vazia e ≤ 200 caracteres;
- `ok` não vazia, ≤ 40 caracteres;
- exatamente 3 distratores, todos ≤ 40 caracteres;
- 4 opções distintas (case-insensitive);
- sem duplicata do enunciado no cache/banco;
- falha → 1 retry com a mensagem de erro no prompt → próximo provider → offline.

Modelos pequenos erram JSON com frequência; a validação não é opcional.

### Cache

Tabela `questions_cache (theme_norm, provider, model, n, payload_json, created_at)`.
Sem workflow de aprovação (decisão do time), serve para performance e para reaproveitar
temas já gerados no mesmo evento.

### Modelo local (Ollama, CPU-only)

| Modelo | RAM aprox. | Velocidade estimada |
|---|---|---|
| `qwen2.5:3b-instruct` Q4_K_M | ~2 GB | 8–15 tok/s |
| `llama3.2:3b` Q4_K_M | ~2 GB | 8–14 tok/s |
| `qwen2.5:1.5b` Q4_K_M | ~1 GB | 20–30 tok/s |

10 perguntas ≈ 500–700 tokens de saída → 45–90 s no 5700U. Aceitável no lobby com
tela de progresso; inviável entre perguntas. Config: `num_ctx=4096`, `format=` JSON
Schema, timeout 120–180 s. Manter 3–4 GB livres para SO + servidor + navegador.

### Hugging Face — nota de escopo

- **HF Hub** = repositório de pesos. É de onde o Ollama baixa o modelo local.
- **HF Inference Providers** = inferência hospedada, via `HF_TOKEN`. Depende de internet,
  cota e provedor — não melhora a resiliência, que é o objetivo do projeto.

Portanto `hf` entra como provider disponível (custo baixo com LangChain), mas a cadeia
de confiança do evento é `gemini → local → offline`.

## 7. Frontend (JS puro)

```
static/
  host.html
  play.html
  css/base.css host.css play.css
  js/
    core/api.js        # fetch com timeout e erro tipado
    core/ws.js         # reconexão com backoff
    core/dom.js        # helpers de render/escape
    core/protocol.js   # tipos de mensagem (espelho do backend)
    host/app.js lobby.js game.js results.js
    play/app.js join.js game.js
```

- Módulos ES relativos, sem bundler e sem dependências externas.
- `host.html` e `play.html` compartilham `css/base.css` e os helpers de `core/`.
- Atalhos mantidos no host: `F` tela cheia, `1–4` respostas (modo local), espaço.
- Tela de geração com progresso e botão de escape ("usar banco offline").
- Sem `innerHTML` com dado de usuário sem `esc()`; manter o helper atual.

## 8. Persistência (SQLite)

Arquivo `data/quiz.db`, WAL, `PRAGMA foreign_keys=ON`. Conexões curtas por operação
(ou threadpool), sem ORM.

```
matches(id, code, mode, theme, provider, created_at, finished_at)
match_teams(id, match_id, name, score, position)
match_players(id, match_id, team_id, nickname, answers_count, correct_count)
questions_cache(id, theme_norm, provider, model, n, payload_json, created_at)
```

- Ranking do evento = consulta sobre `match_teams` (top N por pontuação), substituindo
  o `localStorage`.
- Persistir só o resultado final, não o estado ao vivo.
- `data/quiz.db` no `.gitignore`.

## 9. Modo offline e resiliência

Camadas de degradação, em ordem:

1. Provider primário (Gemini) com retry.
2. Provider secundário configurado (local).
3. Temas prontos em `data/temas/*.json` + banco curado `data/perguntas.json`.
4. Flag `LLM_PROVIDER=offline`: nenhuma chamada externa, jogo 100% funcional.

O modo offline continua exigindo o servidor local (localhost), o que não depende de
internet. Se for necessário um "plano C" de duplo clique, gerar um `offline.html`
autocontido em tempo de release (script de ~20 linhas) — fora do escopo inicial.

## 10. Deploy e operação

- **Local (principal):** `run.sh` / `run.bat` criam venv, instalam dependências,
  validam `.env`, sobem o Uvicorn em `0.0.0.0:8000` e imprimem URL da LAN + QR.
- **Docker (opcional):** `Dockerfile` + `docker-compose.yml` com app e serviço Ollama
  (volume para modelos). Útil para reproduzir o ambiente.
- **Remoto (opcional):** Fly.io/Render/VPS com volume para `data/`. `PUBLIC_URL`
  define o host usado no QR. Evitar free tier com sleep em evento ao vivo.
- **Health check** em `/api/health`: DB acessível, provider configurado, modelo alcançável.
- **Segurança mínima:** `/prepare` com rate limit simples por sala; limites de tamanho
  em `tema` e `n`; token do host e tokens de jogador; `.env` no `.gitignore`.
- Rede: detectar IP da LAN (UDP connect sem envio) e permitir `PUBLIC_URL` como override.
  Wi-Fi de campus com *client isolation* é o maior risco operacional → testar cedo,
  plano B hotspot do notebook.

## 11. Estrutura de pastas

```
app/
  main.py                 # app FastAPI, rotas, static
  config.py               # pydantic-settings
  api/
    routes_rooms.py
    routes_quiz.py        # themes, prepare, ranking, health
    ws.py
    protocol.py           # mensagens Pydantic
  domain/
    models.py             # Pergunta, Team, Player, Room, enums
    scoring.py            # regra de pontos isolada
  game/
    engine.py             # máquina de estados
    room.py               # RoomManager
  llm/
    factory.py
    chain.py
    prompts.py
    validation.py
  db/
    connection.py
    repository.py
    schema.sql
  static/ (ver seção 7)
data/
  perguntas.json
  temas/*.json
  quiz.db (gerado)
tests/
  test_scoring.py
  test_validation.py
  test_engine.py
  test_ws_flow.py
  test_llm_fallback.py
scripts/
  gerar_temas.py          # opcional: pré-aquecer cache/temas
  smoke_ws.py             # 6 clientes simulados
pyproject.toml
.env.example
.gitignore
run.sh / run.bat
Dockerfile / docker-compose.yml
```

## 12. Fases

### Fase 1 — Estrutura + motor + modo local (base sólida) ✅
- [x] `.gitignore`, `pyproject.toml`, `.env.example`, README atualizado
- [x] migrar `perguntas.js` → `data/perguntas.json`; criar `data/temas/*.json`
- [x] FastAPI servindo `static/`, com `/api/health`
- [x] modelos de domínio e `scoring.py`
- [x] `GameEngine` com `alternate` e `simultaneous`
- [x] host em JS puro consumindo o engine via HTTP (paridade com o atual)
- [x] testes de scoring e engine
- [x] flag offline funcional

Critério de aceite: uma partida completa local, sem LLM, igual ao comportamento atual,
mas com estado no servidor e ranking em SQLite.

### Fase 2 — Camada LLM ✅
- [x] factory dos provedores; remover Anthropic
- [x] prompt + structured output + validação + retry
- [x] cache SQLite
- [x] job de geração em background + `generation_status` no lobby
      (implementado via polling HTTP em `GET /api/generate/{job_id}`, não por mensagem WS)
- [x] fallback automático para offline
- [x] testes com `FakeListChatModel` (feito com `FakeStructuredChatModel`, equivalente
      para `with_structured_output`)
- [x] `scripts/gerar_temas.py`

Critério de aceite: escolher tema livre gera perguntas válidas no lobby; derrubar a
rede/API cai para tema pronto sem travar a partida.

### Fase 3 — Multiplayer por celular
- [x] salas, códigos, tokens, `RoomManager`
- [x] WS host/jogador com protocolo validado
- [x] ingresso por time (até 3 membros) + QR
- [x] resposta por time (primeira trava)
- [x] timer e reveal server-side, gabarito protegido
- [x] reconexão e rejoin
- [ ] teste de fluxo WS com 2 times × 3 jogadores
      **Parcial:** há fluxo WS 1v1, trava com 2 membros do mesmo time e capacidade de 3
      via HTTP (409 no quarto). Falta teste com 6 sockets simultâneos e `scripts/smoke_ws.py`.
- [ ] ensaio real com celulares na rede do campus
      **Pendente:** só há roteiro manual no relatório da fase; nenhum ensaio presencial registrado.

Critério de aceite: partida 3v3 completa, com um celular desconectando e voltando sem
travar a rodada.

### Fase 4 — Polimento e entrega
- [ ] ranking/histórico no host
      **Parcial:** o host exibe o ranking persistido (`GET /api/ranking`) no lobby e no fim
      do modo local. Falta histórico de partidas (`matches`), ranking geral no fim do modo
      mobile e a tabela `match_players` (métricas por jogador).
- [ ] script de subida + Docker
      **Parcial:** `run.sh` e `run.bat` funcionam. `Dockerfile` e `docker-compose.yml` não existem.
- [ ] README de operação para o dia do evento
      **Pendente:** o README atual é de desenvolvimento e ainda diz "Celular: fase 3";
      falta roteiro de operação, contingência de Wi-Fi e troubleshooting.
- [ ] ensaio geral e checklist
      **Pendente:** não há checklist operacional nem registro de ensaio geral.

Status da implementação em 2026-11-12 (ver `app/` e `.scratch/quiz-uemg/implemented/`):
suíte com 61 testes passando, 8 módulos JS válidos e nenhuma chamada real de LLM nos testes.

## 13. Testes

- unitários: `scoring`, validação de perguntas, transições do engine, trava de time;
- integração: fluxo WS completo (join → start → answer → reveal → end) com
  `TestClient` do FastAPI;
- LLM: `FakeListChatModel` para caminho feliz, JSON inválido, timeout e fallback;
- smoke: partida inteira em modo offline;
- nenhum teste pode chamar API real (sem cota, determinístico).

## 14. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Client isolation no Wi-Fi do campus | testar na semana 1 da fase 3; hotspot do notebook como plano B |
| Celular dorme/troca de app | token + rejoin + reenvio de estado |
| Modelo local lento no CPU | geração só no lobby, com timeout e fallback; pré-aquecer no `scripts/gerar_temas.py` |
| Latência do Gemini no lobby | job em background + tela de progresso + escape para offline |
| LangChain quebra entre versões | pinar versões exatas no `pyproject.toml` |
| Duas regras de jogo (local x celular) | um motor só, `answer_mode` explícito e testado |
| Vazamento de chave | `.env` + `.gitignore`; chave só no servidor |

## 15. Decisões abertas

1. **Resposta por time no celular:** primeira resposta do time trava a rodada
   (recomendado) ou apenas o "capitão" responde?
2. **Modo celular simultâneo** confirmado? (alternado no celular revelaria a resposta
   ao segundo time)
3. **Deploy remoto** é necessário para a entrega ou basta "roda localmente com um
   comando"? (afeta Docker, `PUBLIC_URL` e escolha de host)
4. **Tema pronto**: os `data/temas/*.json` serão só os 25 atuais reorganizados ou
   você quer um conjunto maior por tema?
