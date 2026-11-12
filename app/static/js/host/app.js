import { api } from "../core/api.js";
import { $, esc, icon } from "../core/dom.js";
import { initMobileHost } from "./mobile.js";

const app = $("#app");
const LETTERS = ["A", "B", "C", "D"];

let themes = [];
let ranking = [];
let game = null;
let hostToken = null;
let animation = 0;
let timeoutRequested = false;
let busy = false;
let selectedMode = "local";
let generatedQuestions = [];
let isGenerating = false;

const fullscreenBtn = $("#fullscreen-btn");
if (fullscreenBtn) {
  fullscreenBtn.addEventListener("click", toggleFullscreen);
}

boot();

async function boot() {
  try {
    [themes, ranking] = await Promise.all([
      api.get("/api/themes"),
      api.get("/api/ranking?limit=5"),
    ]);
  } catch {
    themes = [];
    ranking = [];
  }
  renderLobby();
}

function toggleFullscreen() {
  if (document.fullscreenElement) {
    document.exitFullscreen().catch(() => {});
  } else {
    document.documentElement.requestFullscreen().catch(() => {});
  }
}

function themeIcon(theme) {
  const key = `${theme.id || ""} ${theme.name || ""}`.toLowerCase();
  if (key.includes("anime")) return "torii";
  if (key.includes("filme")) return "clapperboard";
  if (key.includes("serie") || key.includes("série")) return "television";
  if (key.includes("jogo")) return "game-controller";
  if (key.includes("tecnolog")) return "laptop";
  if (key.includes("direito")) return "justice";
  if (key.includes("geral")) return "books";
  return "target";
}

function themePills() {
  const pills = [
    { id: "", icon: "books", name: "Banco geral" },
    ...themes.map((theme) => ({
      id: theme.id,
      icon: themeIcon(theme),
      name: theme.name,
    })),
    { id: "__free__", icon: "light-bulb", name: "Tema livre" },
  ];

  return pills
    .map(
      (pill) => `
        <button
          type="button"
          class="theme-pill ${pill.id === "" ? "active" : ""}"
          data-theme="${esc(pill.id)}"
        >
          ${icon(pill.icon)}
          <span>${esc(pill.name)}</span>
        </button>
      `,
    )
    .join("");
}

function themeOptions() {
  const options = ['<option value="">Banco geral (todas as categorias)</option>'];
  for (const theme of themes) {
    options.push(
      `<option value="${esc(theme.id)}">${esc(theme.name)} (${theme.count})</option>`,
    );
  }
  options.push('<option value="__free__">Tema livre (Gerar com IA)</option>');
  return options.join("");
}

function rankingHtml() {
  if (!ranking.length) {
    return `
      <div class="ranking">
        <div class="card-heading">${icon("trophy")}<h2>Ranking do evento</h2></div>
        <p class="ranking-empty">Nenhuma partida finalizada ainda. Seja o primeiro do pódio!</p>
      </div>
    `;
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
      <div class="card-heading">${icon("trophy")}<h2>Ranking do evento</h2></div>
      <ol>${items}</ol>
    </div>
  `;
}

function renderLobby() {
  cancelAnimationFrame(animation);
  game = null;
  hostToken = null;
  generatedQuestions = [];
  isGenerating = false;

  const record = ranking.length ? ranking[0].score : "—";

  app.innerHTML = `
    <div class="home">
      <section class="hero">
        <div class="hero-stats">
          <span class="hero-stat gold">${icon("trophy")} Recorde: ${record} pts</span>
          <span class="hero-dot">•</span>
          <span class="hero-stat cyan">${icon("lightning")} ${themes.length} temas prontos</span>
          <span class="hero-dot">•</span>
          <span class="hero-stat green">${icon("finish-flag")} ${ranking.length} resultados</span>
        </div>
        <h1 class="hero-title">Quiz <span>UEMG</span> ${icon("graduation-cap")}</h1>
        <p class="hero-sub">Duas equipes, até 3 participantes cada. Quem acumular mais pontos domina o pódio!</p>
      </section>

      <div class="mode-bar">
        <span class="mode-label">Como vai jogar?</span>
        <div class="mode-pills" role="tablist" aria-label="Modo de jogo">
          <button
            type="button"
            id="mode-local"
            class="mode-pill ${selectedMode === "local" ? "active" : ""}"
          >
            ${icon("desktop")} Modo Local
          </button>
          <button
            type="button"
            id="mode-mobile"
            class="mode-pill ${selectedMode === "mobile" ? "active" : ""}"
          >
            ${icon("smartphone")} Modo Celulares
          </button>
        </div>
      </div>

      <div class="home-grid">
        <section class="glass-card team-setup" data-purpose="teams-setup">
          <div class="card-head">
            <div class="card-heading">
              ${icon("crossed-swords")}
              <h2>Escalação das Equipes</h2>
            </div>
          </div>

          <div class="team-side side-blue">
            <div class="side-head">
              <span class="side-label"><span class="side-dot"></span> Lado Azul (Teclas 1 e 2)</span>
              <span class="side-tag">Equipe A</span>
            </div>
            <div class="team-input-row">
              <div class="avatar" aria-hidden="true">${icon("lion")}</div>
              <input id="n1" type="text" value="Equipe 1" maxlength="18" aria-label="Nome da equipe 1">
            </div>
            <p class="side-hint">${icon("group")} 1 a 3 alunos por equipe</p>
          </div>

          <div class="vs-row"><span class="vs-badge">VS</span></div>

          <div class="team-side side-gold">
            <div class="side-head">
              <span class="side-label"><span class="side-dot"></span> Lado Ouro (Teclas 3 e 4)</span>
              <span class="side-tag">Equipe B</span>
            </div>
            <div class="team-input-row">
              <div class="avatar" aria-hidden="true">${icon("lightning")}</div>
              <input id="n2" type="text" value="Equipe 2" maxlength="18" aria-label="Nome da equipe 2">
            </div>
            <p class="side-hint">${icon("group")} 1 a 3 alunos por equipe</p>
          </div>
        </section>

        <section class="glass-card categories" data-purpose="categories-and-ai">
          <div class="card-head">
            <div class="card-heading">
              ${icon("target")}
              <h2>Selecione o tema da partida</h2>
            </div>
          </div>

          <div class="categories-body">
            <div class="theme-panel">
              <div class="theme-pills" role="group" aria-label="Temas">${themePills()}</div>
              <select id="tema" class="visually-hidden" aria-label="Tema">${themeOptions()}</select>
            </div>

            <div id="ai-section" class="ai-bar">
              <div class="ai-badge">
                ${icon("brain")}
                <span>Sabichão IA</span>
              </div>
              <div class="ai-input-wrap">
                <input
                  id="free-theme-input"
                  type="text"
                  maxlength="80"
                  placeholder="Tema personalizado para a IA (ex: História de Minas)"
                >
              </div>
              <button type="button" id="gen-ai-btn" class="ai-btn">${icon("sparkles")} Gerar com IA</button>
              <div id="ai-status-box" class="ai-status-box"></div>
            </div>
          </div>
        </section>
      </div>

      <section class="settings-grid" data-purpose="game-rules-config">
        <div class="setting-card">
          <div>
            <p class="setting-label">Tamanho do Quiz</p>
            <p class="setting-title">Perguntas por partida</p>
          </div>
          <select id="qt" aria-label="Perguntas por partida">
            <option value="6">6 questões</option>
            <option value="10" selected>10 questões</option>
            <option value="14">14 questões</option>
          </select>
        </div>

        <div class="setting-card">
          <div>
            <p class="setting-label">Cronômetro</p>
            <p class="setting-title">Tempo por rodada</p>
          </div>
          <span class="setting-pill">${icon("stopwatch")} Definido pelo servidor</span>
        </div>
      </section>

      <section class="start-area" data-purpose="primary-action">
        <button id="go" class="start-btn">
          <span>Começar Partida!</span>
          <span aria-hidden="true">${icon("rocket")}</span>
        </button>
        <p class="start-hint">Pronto para iniciar? Os cronômetros começam imediatamente!</p>
      </section>

      <section class="ranking-section">
        ${rankingHtml()}
      </section>
    </div>
  `;

  $("#mode-local").addEventListener("click", () => {
    selectedMode = "local";
    $("#mode-local").classList.add("active");
    $("#mode-mobile").classList.remove("active");
  });

  $("#mode-mobile").addEventListener("click", () => {
    selectedMode = "mobile";
    $("#mode-mobile").classList.add("active");
    $("#mode-local").classList.remove("active");
  });

  const temaSelect = $("#tema");
  const freeInput = $("#free-theme-input");

  document.querySelectorAll(".theme-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      temaSelect.value = pill.dataset.theme;
      temaSelect.dispatchEvent(new Event("change"));
      if (pill.dataset.theme === "__free__") freeInput.focus();
    });
  });

  temaSelect.addEventListener("change", () => {
    document.querySelectorAll(".theme-pill").forEach((pill) => {
      pill.classList.toggle("active", pill.dataset.theme === temaSelect.value);
    });
    if (temaSelect.value !== "__free__") generatedQuestions = [];
  });

  freeInput.addEventListener("focus", () => {
    if (temaSelect.value !== "__free__") {
      temaSelect.value = "__free__";
      temaSelect.dispatchEvent(new Event("change"));
    }
  });

  $("#gen-ai-btn").addEventListener("click", handleGenerateAI);
  $("#go").addEventListener("click", startGame);
}

async function handleGenerateAI() {
  if (isGenerating) return;
  const input = $("#free-theme-input");
  const text = (input ? input.value : "").trim();
  const statusBox = $("#ai-status-box");
  const count = Number($("#qt").value) || 10;

  if (!text) {
    if (statusBox) statusBox.innerHTML = `<span class="ai-status" style="color:var(--vermelho);">Digite um tema para gerar.</span>`;
    return;
  }

  isGenerating = true;
  const genBtn = $("#gen-ai-btn");
  if (genBtn) {
    genBtn.disabled = true;
    genBtn.innerHTML = `${icon("sparkles")} Gerando…`;
  }

  if (statusBox) {
    statusBox.innerHTML = `<span class="ai-status">Iniciando geração com IA…</span>`;
  }

  try {
    const jobRes = await api.post("/api/generate", {
      tema: text,
      n: count,
    });

    const jobId = jobRes.job_id;
    await pollGenerationJob(jobId, text, statusBox);
  } catch (err) {
    if (statusBox) {
      statusBox.innerHTML = `<span class="ai-status" style="color:var(--vermelho);">${esc(err.message || "Erro ao solicitar geração")}</span>`;
    }
  } finally {
    isGenerating = false;
    if (genBtn) {
      genBtn.disabled = false;
      genBtn.innerHTML = `${icon("sparkles")} Gerar com IA`;
    }
  }
}

async function pollGenerationJob(jobId, themeText, statusBox) {
  let attempts = 0;
  const maxAttempts = 60;
  while (attempts < maxAttempts) {
    attempts += 1;
    await new Promise((resolve) => setTimeout(resolve, 1000));
    try {
      const res = await api.get(`/api/generate/${encodeURIComponent(jobId)}`);
      if (res.status === "done") {
        generatedQuestions = res.questions || [];
        const providerName = res.provider || "offline";
        const fallbackWarning = res.fallback
          ? `<div class="ai-fallback">${icon("warning")} Provedor indisponível. Fallback offline utilizado!</div>`
          : "";

        if (statusBox) {
          statusBox.innerHTML = `
            <div class="ai-status" style="color:var(--verde);">
              ${icon("check")} ${generatedQuestions.length} perguntas geradas com sucesso! (Provedor: ${esc(providerName)})
            </div>
            ${fallbackWarning}
          `;
        }
        return;
      } else if (res.status === "error") {
        if (statusBox) {
          statusBox.innerHTML = `<span class="ai-status" style="color:var(--vermelho);">${esc(res.detail || "Erro na geração das perguntas")}</span>`;
        }
        return;
      } else {
        if (statusBox) {
          statusBox.innerHTML = `<span class="ai-status"><span class="pulse"></span> Criando perguntas sobre "${esc(themeText)}"… (${attempts}/${maxAttempts})</span>`;
        }
      }
    } catch (err) {
      if (statusBox) {
        statusBox.innerHTML = `<span class="ai-status" style="color:var(--vermelho);">${esc(err.message || "Falha na consulta do status")}</span>`;
      }
      return;
    }
  }

  if (statusBox) {
    statusBox.innerHTML = `
      <div class="ai-status" style="color:var(--vermelho);">Tempo limite de geração excedido.</div>
      <button type="button" id="retry-gen-btn" class="sec" style="margin-top:8px; font-size:1rem; padding:8px 16px;">
        Tentar novamente
      </button>
    `;
    const retryBtn = $("#retry-gen-btn");
    if (retryBtn) {
      retryBtn.addEventListener("click", handleGenerateAI);
    }
  }
}

async function startGame() {
  if (busy) return;
  busy = true;

  const teamNames = [
    $("#n1").value.trim() || "Equipe 1",
    $("#n2").value.trim() || "Equipe 2",
  ];
  const temaSelectVal = $("#tema").value;
  const isFree = temaSelectVal === "__free__";
  const themeId = isFree ? ($("#free-theme-input").value.trim() || "Tema Livre") : temaSelectVal;
  const n = Number($("#qt").value);

  app.innerHTML = '<h1>Preparando…</h1><div class="sub">Configurando a partida</div>';

  try {
    const payload = {
      mode: selectedMode,
      team_names: teamNames,
      theme_id: themeId,
      n,
    };

    if (isFree && generatedQuestions.length) {
      payload.generated_questions = generatedQuestions;
    }

    const response = await api.post("/api/rooms", payload);

    if (selectedMode === "mobile") {
      initMobileHost({
        roomCode: response.code,
        hostToken: response.host_token,
        initialState: response.state,
        onBackToLobby: renderLobby,
      });
    } else {
      game = response.state;
      hostToken = response.host_token;
      renderGame();
    }
  } catch (error) {
    app.innerHTML = `
      <h1>Não deu para começar</h1>
      <div class="sub">${esc(error.message)}</div>
      <button id="back">Voltar</button>
    `;
    $("#back").addEventListener("click", renderLobby);
  } finally {
    busy = false;
  }
}

function scoreboard() {
  return `<div class="score">${game.teams
    .map((team) => {
      const active = game.phase === "question" && team.id === game.turn_team_id;
      return `<div class="team ${active ? "on" : ""}">${esc(team.name)}<b>${team.score}</b></div>`;
    })
    .join("")}</div>`;
}

function wrongOptionIds() {
  if (!game.reveal) return new Set();
  return new Set(
    game.reveal.answers.filter((answer) => !answer.correct).map((answer) => answer.option_id),
  );
}

function optionHtml(option, index, reveal) {
  let classes = "opt";
  if (reveal) {
    if (option.id === reveal.correct_option_id) classes += " ok";
    else if (wrongOptionIds().has(option.id)) classes += " no";
    else classes += " dim";
  }
  return `<button class="${classes}" data-id="${esc(option.id)}" ${reveal ? "disabled" : ""}>
    <i>${LETTERS[index]}</i>${esc(option.text)}
  </button>`;
}

function revealMessage() {
  return game.teams
    .map((team) => {
      const answer = game.reveal.answers.find((item) => item.team_id === team.id);
      if (!answer) return `${esc(team.name)}: ${icon("alarm")} sem resposta`;
      if (answer.correct) return `${esc(team.name)}: ${icon("check")} +${answer.points}`;
      return `${esc(team.name)}: ${icon("x")}`;
    })
    .join(" · ");
}

function renderGame() {
  cancelAnimationFrame(animation);
  if (!game) return renderLobby();
  if (game.phase === "finished") return renderResults();

  const reveal = game.reveal;
  const turn = game.teams.find((team) => team.id === game.turn_team_id);

  app.innerHTML = `
    ${scoreboard()}
    <div class="cat">${esc(game.question.category)}${turn ? ` · vez de ${esc(turn.name)}` : ""}</div>
    <div class="q">${esc(game.question.prompt)}</div>
    <div class="bar"><div id="clock"></div></div>
    <div class="opts">
      ${game.question.options.map((option, index) => optionHtml(option, index, reveal)).join("")}
    </div>
    <div class="msg" id="msg">${reveal ? revealMessage() : ""}</div>
    ${reveal ? `<button id="next" class="sec">${nextLabel()}</button>` : ""}
  `;

  if (reveal) {
    $("#next").addEventListener("click", nextQuestion);
  } else {
    app.querySelectorAll(".opt").forEach((button) => {
      button.addEventListener("click", () => sendAnswer(button.dataset.id));
    });
    animateClock();
  }
}

function nextLabel() {
  return game.index + 1 >= game.total ? "Ver resultado" : "Próxima (Espaço)";
}

function animateClock() {
  cancelAnimationFrame(animation);
  timeoutRequested = false;
  const bar = $("#clock");
  if (!bar) return;

  const total = Math.max(1, game.seconds_left * 1000);
  const end = performance.now() + total;

  const frame = () => {
    const remaining = Math.max(0, end - performance.now());
    bar.style.width = `${(remaining / total) * 100}%`;
    if (remaining <= 0) {
      if (!timeoutRequested) {
        timeoutRequested = true;
        syncState();
      }
      return;
    }
    animation = requestAnimationFrame(frame);
  };
  animation = requestAnimationFrame(frame);
}

async function sendAnswer(optionId) {
  if (busy || !game || game.phase !== "question" || !game.turn_team_id) return;
  busy = true;
  try {
    game = await api.post(
      `/api/rooms/${game.code}/answer`,
      { team_id: game.turn_team_id, option_id: optionId },
      hostToken,
    );
    renderGame();
  } catch (error) {
    flash(error.message);
  } finally {
    busy = false;
  }
}

async function nextQuestion() {
  if (busy || !game) return;
  busy = true;
  try {
    game = await api.post(`/api/rooms/${game.code}/next`, undefined, hostToken);
    if (game.phase === "finished") {
      ranking = await api.get("/api/ranking?limit=5").catch(() => ranking);
      renderResults();
    } else {
      renderGame();
    }
  } catch (error) {
    flash(error.message);
  } finally {
    busy = false;
  }
}

async function syncState() {
  if (!game) return;
  try {
    game = await api.get(`/api/rooms/${game.code}/state`);
    renderGame();
  } catch (error) {
    flash(error.message);
  }
}

function flash(message) {
  const target = $("#msg");
  if (target) target.textContent = message;
}

function renderResults() {
  cancelAnimationFrame(animation);
  const winners = game.winners || [];
  const title = winners.length === 1 ? `${icon("trophy")} ${esc(winners[0])} venceu!` : `${icon("handshake")} Empate!`;

  app.innerHTML = `
    <h1>${title}</h1>
    <div class="score">${game.teams
      .map((team) => `<div class="team">${esc(team.name)}<b>${team.score}</b></div>`)
      .join("")}</div>
    ${rankingHtml()}
    <button id="again">Nova partida</button>
  `;
  $("#again").addEventListener("click", renderLobby);
}

document.addEventListener("keydown", (event) => {
  if (event.target.tagName === "INPUT" || event.target.tagName === "SELECT") return;

  if (event.key === "f" || event.key === "F") {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen();
    return;
  }

  if (!game) return;

  if (event.key === " " && game.phase === "reveal") {
    event.preventDefault();
    nextQuestion();
    return;
  }

  if (game.phase === "question" && ["1", "2", "3", "4"].includes(event.key)) {
    const option = game.question.options[Number(event.key) - 1];
    if (option) sendAnswer(option.id);
  }
});
