import { api } from "../core/api.js";
import { $, esc, icon } from "../core/dom.js";

export function getSavedSession(code) {
  if (!code) return null;
  try {
    const raw = localStorage.getItem(`quiz_player_${code.toUpperCase()}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveSession(session) {
  try {
    localStorage.setItem(`quiz_player_${session.room.toUpperCase()}`, JSON.stringify(session));
  } catch {}
}

export function clearSession(code) {
  if (!code) return;
  try {
    localStorage.removeItem(`quiz_player_${code.toUpperCase()}`);
  } catch {}
}

export async function showJoinScreen(container, initialCode, onJoined) {
  let currentCode = (initialCode || "").toUpperCase().trim();

  if (!currentCode) {
    container.innerHTML = `
      <div class="play-container">
        <h1>Entrar no Quiz ${icon("game-controller")}</h1>
        <div class="sub">Digite o código da sala mostrado na tela do host:</div>
        <input id="room-code-input" type="text" placeholder="CÓDIGO (ex: ABC123)" maxlength="6" style="text-transform:uppercase;">
        <button id="find-room-btn">Continuar</button>
        <div id="join-error" class="hint" style="color:#fecaca;"></div>
      </div>
    `;

    $("#find-room-btn").addEventListener("click", () => {
      const codeVal = $("#room-code-input").value.trim().toUpperCase();
      if (!codeVal) {
        $("#join-error").textContent = "Digite o código da sala.";
        return;
      }
      showJoinScreen(container, codeVal, onJoined);
    });
    return;
  }

  container.innerHTML = `
    <div class="play-container">
      <span class="pulse"></span>
      <div class="sub">Buscando sala ${esc(currentCode)}…</div>
    </div>
  `;

  let joinInfo = null;
  try {
    joinInfo = await api.get(`/api/rooms/${currentCode}/join-info`);
  } catch (error) {
    container.innerHTML = `
      <div class="play-container">
        <h1>Sala não encontrada</h1>
        <div class="sub">${esc(error.message || "Verifique o código e tente novamente.")}</div>
        <button id="retry-btn">Outro código</button>
      </div>
    `;
    $("#retry-btn").addEventListener("click", () => {
      showJoinScreen(container, "", onJoined);
    });
    return;
  }

  if (joinInfo.phase !== "lobby") {
    container.innerHTML = `
      <div class="play-container">
        <h1>Partida em andamento</h1>
        <div class="sub">Esta sala já começou. Espere a próxima partida!</div>
        <button id="retry-btn">Tentar outra sala</button>
      </div>
    `;
    $("#retry-btn").addEventListener("click", () => {
      showJoinScreen(container, "", onJoined);
    });
    return;
  }

  let selectedTeamId = "";
  const renderForm = (errorMessage = "") => {
    container.innerHTML = `
      <div class="play-container">
        <div class="badge">Sala ${esc(joinInfo.code)} · ${esc(joinInfo.theme)}</div>
        <h1>Escolha sua equipe</h1>
        <div class="sub">Máximo de 3 pessoas por equipe</div>

        <div class="teams-grid">
          ${joinInfo.teams
            .map((t) => {
              const full = t.members >= t.capacity;
              const isSelected = selectedTeamId === t.id;
              return `
                <button
                  type="button"
                  class="team-select-btn ${isSelected ? "selected" : ""}"
                  data-team="${esc(t.id)}"
                  ${full ? "disabled" : ""}
                >
                  <span>${esc(t.name)} ${full ? "(Cheia)" : ""}</span>
                  <span class="team-members-count">${t.members}/${t.capacity}</span>
                </button>
              `;
            })
            .join("")}
        </div>

        <input
          id="nickname-input"
          type="text"
          placeholder="Seu apelido (até 18 letras)"
          maxlength="18"
          aria-label="Seu apelido"
        >

        <button id="join-btn" ${!selectedTeamId ? "disabled" : ""}>Entrar no Jogo!</button>
        ${errorMessage ? `<div class="status-toast" role="status">${esc(errorMessage)}</div>` : ""}
      </div>
    `;

    container.querySelectorAll(".team-select-btn").forEach((btn) => {
      if (!btn.disabled) {
        btn.addEventListener("click", () => {
          selectedTeamId = btn.dataset.team;
          renderForm();
        });
      }
    });

    const nickInput = $("#nickname-input");
    const joinBtn = $("#join-btn");

    if (joinBtn && !joinBtn.disabled) {
      joinBtn.addEventListener("click", async () => {
        const nickname = (nickInput ? nickInput.value : "").trim();
        if (!nickname || nickname.length > 18) {
          renderForm("Digite um apelido entre 1 e 18 caracteres.");
          return;
        }
        if (!selectedTeamId) {
          renderForm("Selecione uma equipe antes de entrar.");
          return;
        }

        joinBtn.disabled = true;
        joinBtn.textContent = "Entrando…";
        try {
          const res = await api.post(`/api/rooms/${currentCode}/players`, {
            nickname,
            team_id: selectedTeamId,
          });

          const session = {
            room: currentCode,
            player_id: res.player_id,
            player_token: res.player_token,
            team_id: res.team_id,
            team_name: res.team_name,
            nickname,
          };
          saveSession(session);
          onJoined(session);
        } catch (err) {
          try {
            joinInfo = await api.get(`/api/rooms/${currentCode}/join-info`);
          } catch {}
          renderForm(err.message || "Erro ao entrar na sala.");
        }
      });
    }
  };

  renderForm();
}
