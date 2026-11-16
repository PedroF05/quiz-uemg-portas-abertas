import { api } from "../core/api.js";
import { $, esc, icon } from "../core/dom.js";
import { initSessionHost } from "./session.js";

const app = $("#app");

let themes = [];
let ranking = [];
let history = [];
let busy = false;
let generatedQuestions = [];
let isGenerating = false;

const fullscreenBtn = $("#fullscreen-btn");
if (fullscreenBtn) {
  fullscreenBtn.addEventListener("click", toggleFullscreen);
}

boot();

async function boot() {
  try {
    [themes, ranking, history] = await Promise.all([
      api.get("/api/themes").catch(() => []),
      api.get("/api/ranking?limit=5").catch(() => []),
      api.get("/api/history?limit=5").catch(() => []),
    ]);
  } catch {
    themes = [];
    ranking = [];
    history = [];
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

function formatShortDate(isoString) {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return String(isoString).slice(0, 10);
    const day = String(d.getDate()).padStart(2, "0");
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const hours = String(d.getHours()).padStart(2, "0");
    const minutes = String(d.getMinutes()).padStart(2, "0");
    return `${day}/${month} ${hours}:${minutes}`;
  } catch {
    return String(isoString).slice(0, 10);
  }
}

function historyHtml() {
  if (!history.length) {
    return `
      <div class="history-card">
        <div class="card-heading">${icon("finish-flag")}<h2>Últimas partidas</h2></div>
        <p class="ranking-empty">Nenhuma partida finalizada ainda.</p>
      </div>
    `;
  }

  const items = history
    .map((match) => {
      const dateText = formatShortDate(match.finished_at || match.created_at);
      const modeText =
        match.mode === "session" || match.mode === "mobile" ? "Sessão" : "Local";
      const teams = match.teams || [];
      const maxScore = teams.length ? Math.max(...teams.map((t) => t.score)) : 0;
      const winners = teams.filter((t) => t.score === maxScore).map((t) => t.name);
      let winnerText = "—";
      if (winners.length === 1) {
        winnerText = winners[0];
      } else if (winners.length > 1) {
        winnerText = `Empate (${winners.join(", ")})`;
      }

      return `
        <li>
          <span class="hist-date">${esc(dateText)}</span>
          <span class="hist-theme" title="${esc(match.theme)}">${esc(match.theme)}</span>
          <span class="hist-mode">${esc(modeText)}</span>
          <span class="hist-winner">${icon("trophy")} ${esc(winnerText)}</span>
        </li>
      `;
    })
    .join("");

  return `
    <div class="history-card">
      <div class="card-heading">${icon("finish-flag")}<h2>Últimas partidas</h2></div>
      <ol class="history-list">${items}</ol>
    </div>
  `;
}

function renderLobby() {
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

      <section class="join-shortcut" data-purpose="quick-join">
        <div class="join-shortcut-label">
          ${icon("game-controller")}
          <span>Já tem o código da sala? Entre por aqui</span>
        </div>
        <div class="join-shortcut-form">
          <input
            id="quick-room-code"
            type="text"
            maxlength="6"
            autocomplete="off"
            spellcheck="false"
            placeholder="CÓDIGO"
            aria-label="Código da sala"
          >
          <button type="button" id="quick-join-btn" class="join-enter-btn">Entrar</button>
        </div>
      </section>

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
              <span class="side-label"><span class="side-dot"></span> Lado Azul</span>
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
              <span class="side-label"><span class="side-dot"></span> Lado Ouro</span>
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
        <p class="start-hint">Crie a sessão e compartilhe o QR Code ou o código da sala!</p>
      </section>

      <section class="lobby-bottom-grid">
        ${rankingHtml()}
        ${historyHtml()}
      </section>
    </div>
  `;

  const quickCode = $("#quick-room-code");
  const quickJoinBtn = $("#quick-join-btn");

  const goToPlay = () => {
    const code = (quickCode.value || "").trim().toUpperCase();
    window.location.href = code
      ? `/play?room=${encodeURIComponent(code)}`
      : "/play";
  };

  quickCode.addEventListener("input", () => {
    quickCode.value = quickCode.value.toUpperCase();
  });

  quickCode.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      goToPlay();
    }
  });

  quickJoinBtn.addEventListener("click", goToPlay);

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
  const maxAttempts = 420;
  while (attempts < maxAttempts) {
    attempts += 1;
    await new Promise((resolve) => setTimeout(resolve, 1000));
    try {
      const res = await api.get(`/api/generate/${encodeURIComponent(jobId)}`);
      if (res.status === "done") {
        generatedQuestions = res.questions || [];
        const providerName = res.provider || "offline";
        const fallbackWarning = res.fallback
          ? `<div class="ai-fallback">${icon("warning")} ${esc(res.detail || `Provedor indisponível. Usando ${providerName}.`)}</div>`
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
          statusBox.innerHTML = `<span class="ai-status"><span class="pulse"></span> Criando perguntas sobre "${esc(themeText)}"… ${attempts}s (limite de 420s)</span>`;
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
      mode: "session",
      team_names: teamNames,
      theme_id: themeId,
      n,
    };

    if (isFree && generatedQuestions.length) {
      payload.generated_questions = generatedQuestions;
    }

    const response = await api.post("/api/rooms", payload);

    initSessionHost({
      roomCode: response.code,
      hostToken: response.host_token,
      joinUrl: response.join_url,
      initialState: response.state,
      onBackToLobby: async () => {
        try {
          [ranking, history] = await Promise.all([
            api.get("/api/ranking?limit=5").catch(() => ranking),
            api.get("/api/history?limit=5").catch(() => history),
          ]);
        } catch {}
        renderLobby();
      },
    });
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

document.addEventListener("keydown", (event) => {
  if (event.target.tagName === "INPUT" || event.target.tagName === "SELECT") return;

  if (event.key === "f" || event.key === "F") {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen();
  }
});
