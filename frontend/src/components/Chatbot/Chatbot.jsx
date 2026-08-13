import ChatbotIcon from "./ChatbotIcon";
import { MdKeyboardArrowDown } from "react-icons/md";
import "./Chatbot.css"
import { ChatForm } from "./ChatForm";
import { useState, useEffect, useRef, useCallback } from "react";
import { ChatMessage } from "./ChatMessage"
import { streamChatMessage } from "./api/chatbotClient";

function Chatbot() {

    const [chatHistory, setChatHistory] = useState([]);
    const [conversationId, setConversationId] = useState(null);
    const [isBotTyping, setIsBotTyping] = useState(false);
    const chatBodyRef = useRef(null);
    const [isOpen, setIsOpen] = useState(false);
    const abortControllerRef = useRef(null);

    useEffect(() => {
    if (chatBodyRef.current) {
        chatBodyRef.current.scrollTop = chatBodyRef.current.scrollHeight;
    }
    }, [chatHistory]);

    // cancela qualquer streaming em andamento se o componente desmontar
    useEffect(() => {
        return () => abortControllerRef.current?.abort();
    }, []);

    // atualiza a ultima mensagem do bot no historico (usada durante o streaming)
    const updateLastBotMessage = (updater) => {
        setChatHistory((history) => {
            const next = [...history];
            const lastIndex = next.length - 1;
            if (lastIndex >= 0 && next[lastIndex].role === "model") {
                next[lastIndex] = updater(next[lastIndex]);
            }
            return next;
        });
    };

    const generateBotResponse = useCallback(async (userMessage) => {
        setIsBotTyping(true);

        // placeholder do bot: comeca "pensando" (bolinhas), sem texto ainda
        setChatHistory((history) => [
            ...history,
            { role: "model", text: "", pending: true, statusText: "", error: false },
        ]);

        const controller = new AbortController();
        abortControllerRef.current = controller;

        try {
            await streamChatMessage({
                message: userMessage,
                conversationId,
                signal: controller.signal,
                onSession: (id) => {
                    if (id) setConversationId(id);
                },
                onStatus: () => {
                    // o backend esta consultando uma ferramenta do EcoTrack
                    // (previsao, pontos monitorados, clima, etc.)
                    updateLastBotMessage((msg) => ({
                        ...msg,
                        statusText: "Consultando dados do EcoTrack...",
                    }));
                },
                onDelta: (textChunk) => {
                    updateLastBotMessage((msg) => ({
                        ...msg,
                        text: msg.text + textChunk,
                        pending: false,
                        statusText: "",
                    }));
                },
                onDone: () => {
                    updateLastBotMessage((msg) => ({ ...msg, pending: false }));
                },
                onError: (err) => {
                    updateLastBotMessage((msg) => ({
                        ...msg,
                        text: err.message,
                        pending: false,
                        statusText: "",
                        error: true,
                    }));
                },
            });
        } catch (err) {
            if (err?.name !== "AbortError") {
                updateLastBotMessage((msg) => ({
                    ...msg,
                    text: err?.message || "Falha ao conectar com o EcoTrack AI.",
                    pending: false,
                    statusText: "",
                    error: true,
                }));
            }
        } finally {
            setIsBotTyping(false);
        }
    }, [conversationId]);

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
                        <ChatForm
                            setChatHistory={setChatHistory}
                            generateBotResponse={generateBotResponse}
                            isBotTyping={isBotTyping}
                        />
                    </div>
                </div>
            )}
        </>
    );
}

export default Chatbot;