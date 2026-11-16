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
        <div class="sub">Digite o código da sala mostrado na tela do host (celular ou PC):</div>
        <input id="room-code-input" type="text" placeholder="CÓDIGO (ex: ABC123)" maxlength="6" style="text-transform:uppercase;">
        <button id="find-room-btn">Continuar</button>
        <div id="join-error" class="hint" style="color:#fecaca;"></div>
      </div>
    `;

    const roomInput = $("#room-code-input");
    const submitCode = () => {
      const codeVal = roomInput.value.trim().toUpperCase();
      if (!codeVal) {
        $("#join-error").textContent = "Digite o código da sala.";
        return;
      }
      showJoinScreen(container, codeVal, onJoined);
    };

    $("#find-room-btn").addEventListener("click", submitCode);
    roomInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        submitCode();
      }
    });
    roomInput.focus();
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

  // Mantém a sala na URL para que um F5 no PC ou no celular reconecte sozinho.
  window.history.replaceState(null, "", `/play?room=${encodeURIComponent(currentCode)}`);

  let selectedTeamId = "";
  // Preserva o apelido digitado entre re-renders (troca de equipe, erro de entrada).
  let typedNickname = "";
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
          value="${esc(typedNickname)}"
          aria-label="Seu apelido"
        >

        <button id="join-btn" ${!selectedTeamId ? "disabled" : ""}>Entrar no Jogo!</button>
        <button id="change-room-btn" class="sec">Trocar código</button>
        ${errorMessage ? `<div class="status-toast" role="status">${esc(errorMessage)}</div>` : ""}
      </div>
    `;

    const nickInput = $("#nickname-input");
    const joinBtn = $("#join-btn");
    let submitting = false;

    const syncNickname = () => {
      typedNickname = nickInput ? nickInput.value : typedNickname;
    };

    if (nickInput) {
      nickInput.addEventListener("input", () => {
        typedNickname = nickInput.value;
      });
    }

    container.querySelectorAll(".team-select-btn").forEach((btn) => {
      if (!btn.disabled) {
        btn.addEventListener("click", () => {
          syncNickname();
          selectedTeamId = btn.dataset.team;
          renderForm();
        });
      }
    });

    const submitJoin = async () => {
      if (submitting) return;
      syncNickname();
      const nickname = typedNickname.trim();
      if (!selectedTeamId) {
        renderForm("Selecione uma equipe antes de entrar.");
        return;
      }
      if (!nickname || nickname.length > 18) {
        renderForm("Digite um apelido entre 1 e 18 caracteres.");
        return;
      }

      submitting = true;
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
        syncNickname();
        renderForm(err.message || "Erro ao entrar na sala.");
      }
    };

    joinBtn.addEventListener("click", submitJoin);
    if (nickInput) {
      nickInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          submitJoin();
        }
      });
    }

    $("#change-room-btn").addEventListener("click", () => {
      window.history.replaceState(null, "", "/play");
      showJoinScreen(container, "", onJoined);
    });
  };

  renderForm();
}
