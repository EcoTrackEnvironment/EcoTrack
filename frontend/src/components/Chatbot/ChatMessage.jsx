import ChatbotIcon from "./ChatbotIcon"

export const ChatMessage = ({chat}) => {
  return (
    <div className={`message ${chat.role === "model" ? "bot" : "user"}-message`}>
        {chat.role === "model" && <ChatbotIcon/>} 
        <p className="message-text">
            {chat.text}
        </p>
    </div>
  )
}
