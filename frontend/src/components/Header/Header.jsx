import { useState, useRef, useEffect } from "react";
import { FaBell, FaRegUserCircle } from "react-icons/fa";

import ModalAlertas from "./ModalAlertas";
import "./Header.css";
import logoEcoTrack from "./assets/logo_ecotrack.png";

function Header() {
  const [showNotifs, setShowNotifs] = useState(false);
  const notifRef = useRef(null);

  const [alertas, setAlertas] = useState([
    {
      id: 1,
      tipo: "critico",
      titulo: "Crescimento Crítico Detectado",
      mensagem: "Trecho Km 170 excedeu 25cm de vegetação.",
      tempo: "Há 5 min",
      lido: false,
    },
    {
      id: 2,
      tipo: "alerta",
      titulo: "Equipe Delta Alocada",
      mensagem: "Deslocamento iniciado para o Km 160.",
      tempo: "Há 20 min",
      lido: false,
    },
    {
      id: 3,
      tipo: "info",
      titulo: "Sincronização Concluída",
      mensagem: "Dados de satélite atualizados com sucesso.",
      tempo: "Há 1 hora",
      lido: true,
    },
  ]);

  const naoLidos = alertas.filter((a) => !a.lido).length;

  const marcarTodosComoLidos = () => {
    setAlertas(alertas.map((a) => ({ ...a, lido: true })));
  };

  // Fecha o menu ao clicar fora dele
  useEffect(() => {
    function handleClickOutside(event) {
      if (notifRef.current && !notifRef.current.contains(event.target)) {
        setShowNotifs(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <header className="header">
      <div className="header-esquerda">
        <div className="header-logo">
          <img src={logoEcoTrack} alt="Logo EcoTrack" />
        </div>
        <h1 className="header-titulo">EcoTrack</h1>
      </div>

      <div className="header-direita">
        <span aria-label="Alertas demonstrativos">Alertas em demonstração</span>
        <div className="notif-wrapper" ref={notifRef}>
          <button
            type="button"
            className="header-botao"
            aria-label="Notificações"
            onClick={() => setShowNotifs(!showNotifs)}
          >
            <FaBell />
            {naoLidos > 0 && <span className="notif-badge">{naoLidos}</span>}
          </button>

          {showNotifs && (
            <ModalAlertas
              alertas={alertas}
              marcarTodosComoLidos={marcarTodosComoLidos}
            />
          )}
        </div>

        <div className="header-usuario">
          <FaRegUserCircle />
          <span>Usuário demonstrativo: João Silva</span>
        </div>
      </div>
    </header>
  );
}

export default Header;
