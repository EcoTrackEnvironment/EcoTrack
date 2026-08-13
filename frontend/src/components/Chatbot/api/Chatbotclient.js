// Cliente HTTP para o backend do chatbot EcoTrack (router.py / service.py).
//
// IMPORTANTE: ajuste API_BASE_URL para o endereco onde a sua API FastAPI esta
// rodando. Se o router "chat" (router.py) for incluido na raiz do app
// (app.include_router(create_chat_router())), os caminhos finais sao:
//   POST   {API_BASE_URL}/chat
//   POST   {API_BASE_URL}/chat/stream
//   DELETE {API_BASE_URL}/chat/conversations/{conversation_id}
// Se voce incluir o router com um prefixo (ex: app.include_router(router, prefix="/api")),
// ajuste API_BASE_URL de acordo (ex: "http://localhost:8000/api").
//
// Dica: em vez de fixar a URL aqui, prefira uma variavel de ambiente do seu
// bundler:
//   Vite -> import.meta.env.VITE_ECOTRACK_API_URL
//   CRA  -> process.env.REACT_APP_ECOTRACK_API_URL
const API_BASE_URL = "http://127.0.0.1:8000";

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
    throw await parseErrorResponse(response);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

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
        onSession?.(data.conversation_id);
        break;
      case "status":
        onStatus?.(data);
        break;
      case "delta":
        onDelta?.(data.text ?? "");
        break;
      case "done":
        onDone?.(data);
        break;
      case "error":
        onError?.(new ChatbotApiError(data.message, data.code, data.retryable));
        break;
      default:
        break;
    }
  };

  const consumeBuffer = () => {
    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      if (!rawEvent.trim()) continue;

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
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    consumeBuffer();
  }
}

/** Espelha DELETE /chat/conversations/{conversation_id}. */
export async function deleteConversation(conversationId) {
  if (!conversationId) return;
  await fetch(`${API_BASE_URL}/chat/conversations/${conversationId}`, {
    method: "DELETE",
  });
}