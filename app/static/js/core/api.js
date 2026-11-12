export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(method, path, { body, token, timeout = 20000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["X-Host-Token"] = token;

  try {
    const response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      let detail = data.detail;
      if (detail && typeof detail !== "string") {
        detail = "Dados inválidos.";
      }
      throw new ApiError(detail || `Erro ${response.status}`, response.status);
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new ApiError("O servidor demorou para responder.", 0);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, body, token) => request("POST", path, { body, token }),
};
