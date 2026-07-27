import { FaBell, FaRegUserCircle } from "react-icons/fa";

import "./Header.css";
import logoEcoTrack from "./assets/logo_ecotrack.png";

function Header() {
  return (
    <header className="header">
      <div className="header-esquerda">
        <div className="header-logo">
          <img src={logoEcoTrack} alt="Logo EcoTrack" />
          
        </div>

        <h1 className="header-titulo">
          EcoTrack
        </h1>
      </div>

      <div className="header-direita">
        <button
          type="button"
          className="header-botao"
          aria-label="Notificações"
        >
          <FaBell />
        </button>

        <div className="header-usuario">
          <FaRegUserCircle />
          <span>João Silva</span>
        </div>
      </div>
    </header>
  );
}

export default Header;