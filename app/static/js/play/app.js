import { $, esc, icon } from "../core/dom.js";
import { QuizSocket } from "../core/ws.js";
import { clearSession, getSavedSession, showJoinScreen } from "./join.js";
import {
  renderFinished,
  renderLobby,
  renderQuestion,
  renderReveal,
  renderTeamLocked,
} from "./game.js";

const appContainer = $("#app");
let currentSocket = null;

boot();

function boot() {
  const params = new URLSearchParams(window.location.search);
  const roomCode = (params.get("room") || "").toUpperCase().trim();

  const saved = getSavedSession(roomCode);
  if (saved && saved.player_token) {
    connectPlayer(saved);
  } else {
    showJoinScreen(appContainer, roomCode, (session) => {
      connectPlayer(session);
    });
  }
}

function showPlayerToast(message) {
  const existing = $(".status-toast", appContainer);
  if (existing) {
    existing.remove();
  }
  const toast = document.createElement("div");
  toast.className = "status-toast";
  toast.style.marginTop = "12px";
  toast.style.background = "var(--vermelho)";
  toast.style.color = "var(--branco)";
  toast.innerHTML = `${icon("warning")} ${esc(message)}`;
  const container = $(".play-container", appContainer) || appContainer;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function connectPlayer(session) {
  if (currentSocket) {
    currentSocket.close();
  }

  renderLobby(appContainer, session);

  const wsPath = `/ws/player?room=${encodeURIComponent(session.room)}&token=${encodeURIComponent(session.player_token)}`;

  currentSocket = new QuizSocket(wsPath, {
    onOpen: () => {},
    onMessage: (msg) => {
      handleServerMessage(session, msg);
    },
    onClose: (event) => {
      if (event.code === 1008) {
        clearSession(session.room);
        showJoinScreen(appContainer, session.room, (newSession) => {
          connectPlayer(newSession);
        });
      }
    },
    onError: () => {},
  });

  currentSocket.connect();
}

function handleServerMessage(session, msg) {
  if (msg.type === "error") {
    showPlayerToast(msg.detail || "Erro inesperado.");
  } else if (msg.type === "lobby") {
    renderLobby(appContainer, session);
  } else if (msg.type === "question") {
    renderQuestion(appContainer, session, msg, (optionId) => {
      if (currentSocket) {
        currentSocket.send({ type: "answer", option_id: optionId });
      }
    });
  } else if (msg.type === "team_locked") {
    if (msg.team_id === session.team_id) {
      renderTeamLocked(appContainer, session);
    }
  } else if (msg.type === "reveal") {
    renderReveal(appContainer, session, msg);
  } else if (msg.type === "finished") {
    renderFinished(appContainer, session, msg, () => {
      clearSession(session.room);
      window.location.href = `/play?room=${encodeURIComponent(session.room)}`;
    });
  }
}
