import { FaArrowUp } from "react-icons/fa";
import { useRef } from "react"

export const ChatForm = ({ setChatHistory, generateBotResponse, isBotTyping }) => {

  const inputRef = useRef();

  const handleFormSubmit = (e) => {
    e.preventDefault()
    if (isBotTyping) return;

    const userMessage = inputRef.current.value.trim()
    if (!userMessage) return;

    inputRef.current.value = "";

    // Atualiza o histórico de mensagens
    setChatHistory(history => [...history, {role: "user", text: userMessage}]);

    // Chama o backend (EcoTrack chatbot) via streaming
    generateBotResponse(userMessage);
  } 

  return (
    <form action="#" className="chat-form" onSubmit={handleFormSubmit}>
        <input
          ref={inputRef}
          type="text"
          placeholder={isBotTyping ? "Aguarde a resposta..." : "Digite sua mensagem..."}
          className="message-input"
          disabled={isBotTyping}
          required
        />
        <button disabled={isBotTyping}><FaArrowUp size={12}/></button>
    </form>
  )
}