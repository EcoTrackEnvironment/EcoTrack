import { FaArrowUp } from "react-icons/fa";
import { useRef } from "react"

export const ChatForm = ({setChatHistory}) => {

  const inputRef = useRef();

  const handleFormSubmit = (e) => {
    e.preventDefault()
    const userMessage = inputRef.current.value.trim()
    if (!userMessage) return;

    inputRef.current.value = "";
    console.log(userMessage);

    // Atualiza o histórico de mensagens
    setChatHistory(history => [...history, {role: "user", text: userMessage}]);


    // SIMULAÇÃO DE RESPOSTA!!!! 
    // setTimeout(() => {
    //     setChatHistory(history => [...history, { role: "model", text: "Esta é uma resposta simulada do sistema EcoTrack AI." }]);
    // }, 1000);
  } 

  return (
    <form action="#" className="chat-form" onSubmit={handleFormSubmit}>
        <input ref={inputRef} type="text" placeholder="Digite sua mensagem..." className="message-input" required/>
        <button><FaArrowUp size={12}/></button>
    </form>
  )
}
