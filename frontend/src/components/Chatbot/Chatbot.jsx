import ChatbotIcon from "./ChatbotIcon";
import { MdKeyboardArrowDown } from "react-icons/md";
import "./Chatbot.css"
import { ChatForm } from "./ChatForm";
import { useState, useEffect, useRef} from "react";
import { ChatMessage } from "./ChatMessage"

function Chatbot() {

    const [chatHistory, setChatHistory] = useState([]);
    const chatBodyRef = useRef(null);
    const [isOpen, setIsOpen] = useState(false);

    useEffect(() => {
    if (chatBodyRef.current) {
        chatBodyRef.current.scrollTop = chatBodyRef.current.scrollHeight;
    }
    }, [chatHistory]);

    return (
        <>
            {/* Botão flutuante (Renderizado quando o chat está fechado) */}
            {!isOpen && (
                <button className="chatbot-toggler" onClick={() => setIsOpen(true)}>
                    <ChatbotIcon />
                </button>
            )}

            {/* Janela do chatbot (Renderizada quando o chat está aberto) */}
            {isOpen && (
                <div className="chatbot-popup">
                    
                    {/* chatbot header */}
                    <div className="chatbot-header">
                        <div className="header-info">
                            <ChatbotIcon/>
                            <h2 className="logo-text">EcoTrack AI</h2>
                        </div>
                        {/* Gatilho para minimizar a janela */}
                        <button onClick={() => setIsOpen(false)}>
                            <MdKeyboardArrowDown size={24}/>
                        </button>
                    </div>

                    {/* chatbot body */}
                    <div className="chat-body" ref={chatBodyRef}>
                        <div className="message bot-message">
                            <ChatbotIcon/> 
                            <p className="message-text">
                                Olá!👋<br/> Como posso te ajudar hoje?
                            </p>
                        </div>
                        {chatHistory.map((chat, index) => 
                            <ChatMessage key={index} chat={chat}/>
                        )}
                    </div>

                    {/* chatbot footer */}
                    <div className="chat-footer">
                        <ChatForm setChatHistory={setChatHistory}/>
                    </div>
                </div>
            )}
        </>
    );
}

export default Chatbot;