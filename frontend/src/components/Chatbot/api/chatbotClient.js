// Cliente HTTP para o backend do chatbot EcoTrack (router.py / service.py).
//
// Configure VITE_ECOTRACK_API_URL para o endereco da API FastAPI. Se o router
// "chat" (router.py) for incluido na raiz do app
// (app.include_router(create_chat_router())), os caminhos finais sao:
//   POST   {API_BASE_URL}/chat
//   POST   {API_BASE_URL}/chat/stream
//   DELETE {API_BASE_URL}/chat/conversations/{conversation_id}
// Se voce incluir o router com um prefixo (ex: app.include_router(router, prefix="/api")),
// ajuste API_BASE_URL de acordo (ex: "http://localhost:8000/api").
//
// A URL fica centralizada em src/api/client.js e tem fallback local.
import { API_BASE_URL } from "../../../api/client";

export class ChatbotApiError extends Error {
  constructor(message, code, retryable = false) {
    super(message || "Nao foi possivel falar com o EcoTrack AI.");
    this.name = "ChatbotApiError";
    this.code = code || "UNKNOWN_ERROR";
    this.retryable = Boolean(retryable);
  }
}

async function parseErrorResponse(response) {
  try {
    const body = await response.json();
    const detail = body?.detail ?? body ?? {};
    return new ChatbotApiError(detail.message, detail.code, detail.retryable);
  } catch {
    return new ChatbotApiError(
      "Nao foi possivel falar com o EcoTrack AI.",
      "UNKNOWN_ERROR"
    );
  }
}

/**
 * Envio simples (sem streaming). Espelha POST /chat.
 * Retorna { conversation_id, message, model, usage }.
 */
export async function sendChatMessage(message, conversationId, { signal } = {}) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId ?? null }),
    signal,
  });

  if (!response.ok) {
    throw await parseErrorResponse(response);
  }
  return response.json();
}

/**
 * Envio com streaming (SSE via fetch, ja que EventSource nao suporta POST).
 * Espelha POST /chat/stream, que emite os eventos: session, status, delta,
 * done e error (ver StreamEvent em schemas.py e _sse() em router.py).
 *
 * Uso:
 *   await streamChatMessage({
 *     message: "...",
 *     conversationId,
 *     signal: controller.signal,
 *     onSession: (id) => {...},
 *     onStatus:  (data) => {...},   // { stage, tool }
 *     onDelta:   (text) => {...},   // pedaco de texto do modelo
 *     onDone:    (data) => {...},   // { model, usage }
 *     onError:   (err) => {...},    // ChatbotApiError
 *   });
 */
export async function streamChatMessage({
  message,
  conversationId,
  signal,
  onSession,
  onStatus,
  onDelta,
  onDone,
  onError,
}) {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId ?? null }),
    signal,
  });

  if (!response.ok || !response.body) {
    if (!response.ok) throw await parseErrorResponse(response);
    const error = new ChatbotApiError(
      "O servidor nao disponibilizou streaming.",
      "STREAM_UNAVAILABLE",
      true
    );
    error.fallbackAllowed = true;
    throw error;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let receivedUsefulEvent = false;
  let terminal = false;

  const dispatch = (eventName, dataStr) => {
    let data = {};
    if (dataStr) {
      try {
        data = JSON.parse(dataStr);
      } catch {
        return; // evento malformado: ignora silenciosamente
      }
    }
    switch (eventName) {
      case "session":
        receivedUsefulEvent = true;
        onSession?.(data.conversation_id);
        break;
      case "status":
        receivedUsefulEvent = true;
        onStatus?.(data);
        break;
      case "delta":
        receivedUsefulEvent = true;
        onDelta?.(data.text ?? "");
        break;
      case "done":
        receivedUsefulEvent = true;
        terminal = true;
        onDone?.(data);
        break;
      case "error":
        receivedUsefulEvent = true;
        terminal = true;
        onError?.(new ChatbotApiError(data.message, data.code, data.retryable));
        break;
      default:
        break;
    }
  };

  const parseEvent = (rawEvent) => {
    if (!rawEvent.trim()) return;

    let eventName = "message";
    const dataLines = [];
    for (const line of rawEvent.split("\n")) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }
    dispatch(eventName, dataLines.join("\n"));
  };

  const consumeBuffer = (flush = false) => {
    let match;
    while ((match = /\r?\n\r?\n/.exec(buffer)) !== null) {
      const rawEvent = buffer.slice(0, match.index).replace(/\r/g, "");
      buffer = buffer.slice(match.index + match[0].length);
      if (!rawEvent.trim()) continue;
      parseEvent(rawEvent);
    }
    if (flush && buffer.trim()) {
      parseEvent(buffer.replace(/\r/g, ""));
      buffer = "";
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    consumeBuffer();
  }
  buffer += decoder.decode();
  consumeBuffer(true);
  if (!terminal) {
    const error = new ChatbotApiError("A resposta foi interrompida antes de terminar.", "STREAM_INCOMPLETE", true);
    error.receivedUsefulEvent = receivedUsefulEvent;
    throw error;
  }
  return { receivedUsefulEvent };
}

/** Espelha DELETE /chat/conversations/{conversation_id}. */
export async function deleteConversation(conversationId) {
  if (!conversationId) return;
  await fetch(`${API_BASE_URL}/chat/conversations/${conversationId}`, {
    method: "DELETE",
  });
}
