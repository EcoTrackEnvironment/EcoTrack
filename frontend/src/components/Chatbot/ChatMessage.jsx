import ChatbotIcon from "./ChatbotIcon"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

export const ChatMessage = ({chat}) => {
  const messageClasses = [
    "message",
    chat.role === "model" ? "bot-message" : "user-message",
    chat.error ? "error-message" : "",
  ].filter(Boolean).join(" ");

  return (
    <div className={messageClasses}>
        {chat.role === "model" && <ChatbotIcon/>}
        {chat.pending ? (
            <div className="message-text thinking-indicator">
                {chat.statusText ? (
                    <span className="status-text">{chat.statusText}</span>
                ) : (
                    <>
                        <span className="dot"></span>
                        <span className="dot"></span>
                        <span className="dot"></span>
                    </>
                )}
            </div>
        ) : chat.role === "model" ? (
            // Respostas do bot vem em Markdown (negrito, listas, etc.) -
            // renderiza formatado em vez de mostrar os asteriscos crus.
            <div className="message-text markdown-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {chat.text}
                </ReactMarkdown>
            </div>
        ) : (
            // Mensagens do usuario continuam como texto puro (nao interpretamos
            // markdown do que a pessoa digitou).
            <p className="message-text">
                {chat.text}
            </p>
        )}
    </div>
  )
}