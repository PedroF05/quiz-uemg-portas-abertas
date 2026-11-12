export class QuizSocket {
  constructor(url, { onMessage, onOpen, onClose, onError } = {}) {
    this.path = url;
    this.onMessage = onMessage || (() => {});
    this.onOpen = onOpen || (() => {});
    this.onClose = onClose || (() => {});
    this.onError = onError || (() => {});
    this.socket = null;
    this.retryDelay = 1000;
    this.maxRetryDelay = 8000;
    this.closedManually = false;
    this.timer = null;
  }

  resolveUrl(path) {
    if (path.startsWith("ws://") || path.startsWith("wss://")) {
      return path;
    }
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}${path}`;
  }

  connect() {
    this.closedManually = false;
    clearTimeout(this.timer);
    const fullUrl = this.resolveUrl(this.path);

    try {
      this.socket = new WebSocket(fullUrl);
    } catch (err) {
      this.onError(err);
      this.scheduleReconnect();
      return;
    }

    this.socket.addEventListener("open", () => {
      this.retryDelay = 1000;
      this.onOpen();
    });

    this.socket.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);
        this.onMessage(data);
      } catch (err) {
        this.onError(err);
      }
    });

    this.socket.addEventListener("close", (event) => {
      this.onClose(event);
      if (!this.closedManually && event.code !== 1008) {
        this.scheduleReconnect();
      }
    });

    this.socket.addEventListener("error", (event) => {
      this.onError(event);
    });
  }

  scheduleReconnect() {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.retryDelay = Math.min(this.retryDelay * 1.5, this.maxRetryDelay);
      this.connect();
    }, this.retryDelay);
  }

  send(data) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  close() {
    this.closedManually = true;
    clearTimeout(this.timer);
    if (this.socket) {
      this.socket.close();
    }
  }
}
