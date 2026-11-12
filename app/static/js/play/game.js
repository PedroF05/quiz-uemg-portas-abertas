import { $, esc, icon } from "../core/dom.js";

const LETTERS = ["A", "B", "C", "D"];
let clockAnimation = 0;

export function renderLobby(container, session) {
  cancelAnimationFrame(clockAnimation);
  container.innerHTML = `
    <div class="play-container">
      <div class="team-badge">${esc(session.team_name)}</div>
      <h1>Olá, ${esc(session.nickname)}!</h1>
      <div class="sub">Você está conectado à sala <b>${esc(session.room)}</b>.</div>
      <div class="locked-card" style="margin-top:20px;">
        <span class="pulse"></span> Aguardando o host começar a partida…
      </div>
    </div>
  `;
}

export function renderQuestion(container, session, questionMsg, onAnswer) {
  cancelAnimationFrame(clockAnimation);
  const totalSeconds = Math.max(1, questionMsg.seconds_left || 20);

  container.innerHTML = `
    <div class="play-container">
      <div class="row" style="width:100%; justify-content:space-between;">
        <div class="badge">${esc(questionMsg.category || "Quiz")}</div>
        <div class="badge" style="background:var(--azul-medio);">${esc(session.team_name)}</div>
      </div>

      <div class="bar"><div id="play-clock" style="width:100%;"></div></div>

      <div class="q" style="font-size:1.4rem; margin:10px 0;">${esc(questionMsg.prompt)}</div>

      <div class="play-opts" id="play-opts">
        ${questionMsg.options
          .map((opt, idx) => `
            <button class="play-opt" data-id="${esc(opt.id)}">
              <i>${LETTERS[idx]}</i>
              <span>${esc(opt.text)}</span>
            </button>
          `)
          .join("")}
      </div>
    </div>
  `;

  const bar = $("#play-clock", container);
  const startTime = performance.now();
  const endTime = startTime + totalSeconds * 1000;

  const tick = () => {
    const remaining = Math.max(0, endTime - performance.now());
    if (bar) {
      bar.style.width = `${(remaining / (totalSeconds * 1000)) * 100}%`;
    }
    if (remaining > 0) {
      clockAnimation = requestAnimationFrame(tick);
    }
  };
  clockAnimation = requestAnimationFrame(tick);

  let answered = false;
  container.querySelectorAll(".play-opt").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (answered) return;
      answered = true;
      btn.classList.add("selected");
      container.querySelectorAll(".play-opt").forEach((b) => {
        b.disabled = true;
      });
      onAnswer(btn.dataset.id);
    });
  });
}

export function renderTeamLocked(container, session) {
  const optsContainer = $("#play-opts", container);
  if (optsContainer) {
    optsContainer.querySelectorAll(".play-opt").forEach((b) => {
      b.disabled = true;
    });
  }

  const existingBanner = $(".locked-card", container);
  if (!existingBanner) {
    const banner = document.createElement("div");
    banner.className = "locked-card";
    banner.style.marginTop = "16px";
    banner.innerHTML = `${icon("lock")} <b>Sua equipe já respondeu!</b><br><span class="hint">Aguardando reveal…</span>`;
    const wrap = $(".play-container", container);
    if (wrap) wrap.appendChild(banner);
  }
}

export function renderReveal(container, session, revealMsg) {
  cancelAnimationFrame(clockAnimation);
  const myAnswer = revealMsg.answers.find((a) => a.team_id === session.team_id);
  let statusBanner = "";

  if (!myAnswer) {
    statusBanner = `<div class="reveal-banner neutral">${icon("alarm")} Sua equipe não respondeu a tempo!</div>`;
  } else if (myAnswer.correct) {
    statusBanner = `<div class="reveal-banner correct">${icon("party")} Resposta correta! +${myAnswer.points} pts</div>`;
  } else {
    statusBanner = `<div class="reveal-banner wrong">${icon("x")} Resposta incorreta! 0 pts</div>`;
  }

  const scoresHtml = revealMsg.teams
    .map((t) => `<div>${esc(t.name)}: <b>${t.score} pts</b></div>`)
    .join(" · ");

  container.innerHTML = `
    <div class="play-container">
      <div class="team-badge">${esc(session.team_name)}</div>
      ${statusBanner}
      <div class="locked-card" style="margin-top:10px; width:100%;">
        <b>Placar atual:</b><br>${scoresHtml}
      </div>
      <div class="hint" style="margin-top:14px;">Aguardando o host avançar para a próxima pergunta…</div>
    </div>
  `;
}

export function renderFinished(container, session, finishedMsg, onPlayAgain) {
  cancelAnimationFrame(clockAnimation);
  const winners = finishedMsg.winners || [];
  const isWinner = winners.includes(session.team_name);
  const title = isWinner ? `${icon("trophy")} Sua equipe venceu!` : "Fim de jogo!";

  const scoresList = (finishedMsg.teams || [])
    .map((t) => `<li>${esc(t.name)}: <b>${t.score} pts</b></li>`)
    .join("");

  container.innerHTML = `
    <div class="play-container">
      <h1>${title}</h1>
      <div class="sub">Obrigado por jogar no UEMG Portas Abertas!</div>

      <div class="locked-card" style="width:100%;">
        <b>Classificação final:</b>
        <ol style="margin:10px 0 0 20px;">${scoresList}</ol>
      </div>

      <button id="play-again-btn" style="margin-top:20px;">Jogar Novamente</button>
    </div>
  `;

  $("#play-again-btn", container).addEventListener("click", onPlayAgain);
}
