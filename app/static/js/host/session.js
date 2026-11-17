import { api } from "../core/api.js";
import { $, esc, icon } from "../core/dom.js";
import { QuizSocket } from "../core/ws.js";

const LETTERS = ["A", "B", "C", "D"];
const DIFFICULTY_LABELS = {
  facil: "Fácil",
  medio: "Médio",
  dificil: "Difícil",
};

function difficultyTag(question) {
  const diff = question?.difficulty || "facil";
  const weight = question?.weight || 1;
  const label = DIFFICULTY_LABELS[diff] || "Fácil";
  return `${label} (${weight}x)`;
}
let clockAnimation = 0;
let hostSocket = null;
let currentGameState = null;

export function initSessionHost({ roomCode, hostToken, joinUrl, initialState, onBackToLobby }) {
  const app = $("#app");

  currentGameState = initialState;

  detachHostSession();

  const wsPath = `/ws/host?room=${encodeURIComponent(roomCode)}&token=${encodeURIComponent(hostToken)}`;

  hostSocket = new QuizSocket(wsPath, {
    onOpen: () => {},
    onMessage: (msg) => {
      if (msg.type === "error") {
        showHostError(msg.detail || "Erro inesperado.");
        return;
      }
      const state = msg.state || msg;
      if (state && state.phase) {
        currentGameState = state;
        renderState(app, state, joinUrl, onBackToLobby);
      }
    },
    onClose: () => {},
    onError: () => {},
  });

  hostSocket.connect();
  renderState(app, initialState, joinUrl, onBackToLobby);

  const keyHandler = (event) => {
    if (!currentGameState) return;
    if (event.key !== " ") return;
    // Let focused buttons handle Space themselves (avoids sending "next" twice).
    if (event.target?.tagName === "BUTTON" || event.target?.id === "session-next-btn") return;
    if (currentGameState.phase === "reveal") {
      event.preventDefault();
      sendNext();
    }
  };

  window.__sessionHostKeyHandler = keyHandler;
  document.addEventListener("keydown", keyHandler);
}

function detachHostSession() {
  if (window.__sessionHostKeyHandler) {
    document.removeEventListener("keydown", window.__sessionHostKeyHandler);
    window.__sessionHostKeyHandler = null;
  }

  if (hostSocket) {
    hostSocket.close();
    hostSocket = null;
  }
}

function sendStart() {
  if (hostSocket) {
    hostSocket.send({ type: "start" });
  }
}

function sendNext() {
  if (hostSocket) {
    hostSocket.send({ type: "next" });
  }
}

function showHostError(message) {
  const target = $("#msg") || $("#host-msg");
  if (target) {
    target.innerHTML = `<span style="color:var(--vermelho); font-weight:700;">${icon("warning")} ${esc(message)}</span>`;
  }
}

function renderState(app, state, joinUrl, onBackToLobby) {
  cancelAnimationFrame(clockAnimation);

  if (state.phase === "lobby") {
    renderLobby(app, state, joinUrl);
  } else if (state.phase === "question") {
    renderQuestion(app, state);
  } else if (state.phase === "reveal") {
    renderReveal(app, state);
  } else if (state.phase === "finished") {
    renderFinished(app, state, onBackToLobby);
  }
}

function renderLobby(app, state, joinUrl) {
  const teamsHtml = state.teams
    .map((team) => {
      const players = team.players || [];
      const chips = players.length
        ? players
            .map((p) => `<span class="player-chip">${esc(p.nickname)}</span>`)
            .join("")
        : `<span class="empty-chip">Nenhum jogador conectado</span>`;

      return `
        <div class="lobby-team-col">
          <h3>
            <span>${esc(team.name)}</span>
            <span>${players.length}/3</span>
          </h3>
          <div class="player-chips">${chips}</div>
        </div>
      `;
    })
    .join("");

  const totalPlayers = state.teams.reduce(
    (sum, t) => sum + (t.players ? t.players.length : 0),
    0,
  );

  const playUrl = joinUrl || `${window.location.origin}/play`;

  app.innerHTML = `
    <div class="lobby-box">
      <div class="room-code-tag">CÓDIGO: ${esc(state.code)}</div>
      <div class="sub">Escaneie o QR Code no celular ou acesse pelo navegador (celular ou PC) e digite o código:</div>

      <div class="join-url-pill">${icon("laptop")}<span>${esc(playUrl)}</span></div>

      <div class="qr-card">
        <img src="/api/rooms/${encodeURIComponent(state.code)}/qr.png" alt="QR Code da Sala">
      </div>

      <div class="lobby-teams">${teamsHtml}</div>

      <button id="start-session-btn" style="padding:16px 36px; font-size:1.4rem;" ${totalPlayers === 0 ? "disabled" : ""}>
        Começar Partida! (${totalPlayers}/6 conectados)
      </button>

      <div id="host-msg" class="msg" style="color:var(--vermelho);"></div>
      <div class="hint">Os jogadores escolhem a equipe pelo celular ou PC · Quem responder primeiro pontua</div>
    </div>
  `;

  const startBtn = $("#start-session-btn");
  if (startBtn) {
    startBtn.addEventListener("click", () => {
      sendStart();
    });
  }
}

function scoreboard(state) {
  return `<div class="score">${state.teams
    .map((team) => {
      const active = state.phase === "question" && team.answered;
      return `
        <div class="team ${active ? "on" : ""}">
          ${esc(team.name)}
          <b>${team.score}</b>
          <div class="hint" style="font-size:0.9rem; margin-top:4px;">
            ${team.answered ? `${icon("check")} Respondeu` : "Aguardando…"}
          </div>
        </div>
      `;
    })
    .join("")}</div>`;
}

function wrongOptionIds(state) {
  if (!state.reveal || !state.reveal.answers) return new Set();
  return new Set(
    state.reveal.answers
      .filter((a) => !a.correct)
      .map((a) => a.option_id),
  );
}

function optionHtml(option, index, reveal, state) {
  let classes = "opt readonly-opt";
  if (reveal) {
    if (option.id === reveal.correct_option_id) classes += " ok";
    else if (wrongOptionIds(state).has(option.id)) classes += " no";
    else classes += " dim";
  }
  return `
    <div class="${classes}">
      <i>${LETTERS[index]}</i>${esc(option.text)}
    </div>
  `;
}

function renderQuestion(app, state) {
  app.innerHTML = `
    <div class="game-screen">
      ${scoreboard(state)}
      <div class="cat">${esc(state.question.category)} · ${esc(difficultyTag(state.question))} · Rodada Simultânea</div>
      <div class="q">${esc(state.question.prompt)}</div>
      <div class="bar"><div id="clock"></div></div>
      <div class="opts">
        ${state.question.options.map((opt, i) => optionHtml(opt, i, null, state)).join("")}
      </div>
      <div class="msg" id="msg">${icon("laptop")} ${icon("smartphone")} Respondam pelo celular ou PC!</div>
    </div>
  `;

  animateClock(state.seconds_left);
}

function revealMessage(state) {
  return state.teams
    .map((team) => {
      const answer = state.reveal.answers.find((item) => item.team_id === team.id);
      if (!answer) return `${esc(team.name)}: ${icon("alarm")} sem resposta`;
      if (answer.correct) return `${esc(team.name)}: ${icon("check")} +${answer.points}`;
      return `${esc(team.name)}: ${icon("x")}`;
    })
    .join(" · ");
}

function renderReveal(app, state) {
  const nextText = state.index + 1 >= state.total ? "Ver Resultado Final" : "Próxima Pergunta (Espaço)";

  app.innerHTML = `
    <div class="game-screen">
      ${scoreboard(state)}
      <div class="cat">${esc(state.question.category)} · ${esc(difficultyTag(state.question))}</div>
      <div class="q">${esc(state.question.prompt)}</div>
      <div class="bar"><div id="clock" style="width:0%;"></div></div>
      <div class="opts">
        ${state.question.options.map((opt, i) => optionHtml(opt, i, state.reveal, state)).join("")}
      </div>
      <div class="msg" id="msg">${revealMessage(state)}</div>
      <button id="session-next-btn" class="sec">${nextText}</button>
    </div>
  `;

  $("#session-next-btn").addEventListener("click", () => {
    sendNext();
  });
}

function rankingHtml(ranking) {
  if (!ranking || !ranking.length) {
    return "";
  }

  const items = ranking
    .map(
      (entry, index) => `
        <li>
          <span class="rank-pos">${index + 1}</span>
          <span class="rank-name">${esc(entry.name)}</span>
          <span class="rank-score">${entry.score} pts</span>
        </li>
      `,
    )
    .join("");

  return `
    <div class="ranking">
      <div class="card-heading">${icon("trophy")}<h2>Ranking Geral do Evento</h2></div>
      <ol>${items}</ol>
    </div>
  `;
}

function renderFinished(app, state, onBackToLobby) {
  const winners = state.winners || [];
  const title = winners.length === 1 ? `${icon("trophy")} ${esc(winners[0])} venceu!` : `${icon("handshake")} Empate!`;

  app.innerHTML = `
    <div class="game-screen results-screen">
      <h1>${title}</h1>
      <div class="score">
        ${state.teams.map((t) => `<div class="team">${esc(t.name)}<b>${t.score}</b></div>`).join("")}
      </div>
      <div id="session-ranking-wrap"></div>
      <button id="session-again-btn">Nova Partida</button>
    </div>
  `;

  api
    .get("/api/ranking?limit=5")
    .then((ranking) => {
      const wrap = $("#session-ranking-wrap");
      if (wrap) {
        wrap.innerHTML = rankingHtml(ranking);
      }
    })
    .catch(() => {});

  $("#session-again-btn").addEventListener("click", () => {
    detachHostSession();
    onBackToLobby();
  });
}

function animateClock(secondsLeft) {
  cancelAnimationFrame(clockAnimation);
  const bar = $("#clock");
  if (!bar) return;

  const total = Math.max(1, secondsLeft * 1000);
  const end = performance.now() + total;

  const frame = () => {
    const remaining = Math.max(0, end - performance.now());
    bar.style.width = `${(remaining / total) * 100}%`;
    if (remaining > 0) {
      clockAnimation = requestAnimationFrame(frame);
    }
  };
  clockAnimation = requestAnimationFrame(frame);
}
