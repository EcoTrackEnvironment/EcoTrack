import { NavLink, useNavigate } from "react-router-dom";
import {
  FaChartPie,
  FaLeaf,
  FaCut,
  FaUser,
  FaCog,
  FaSignOutAlt,
} from "react-icons/fa";

import "./Sidebar.css";

function Sidebar() {
  const navigate = useNavigate();

  const criarClasseDoLink = ({ isActive }) => {
    return `sidebar-link ${isActive ? "ativo" : ""}`;
  };

  const handleLogout = () => {
    navigate("/");
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-topo">
        <div className="sidebar-logo">JS</div>

        <nav className="sidebar-menu">
          <NavLink
            to="/dashboard"
            className={criarClasseDoLink}
            title="Dashboard principal"
          >
            <FaChartPie />
          </NavLink>

          <NavLink
            to="/indicadores-ambientais"
            className={criarClasseDoLink}
            title="Indicadores ambientais"
          >
            <FaLeaf />
          </NavLink>

          <NavLink
            to="/registro-cortes"
            className={criarClasseDoLink}
            title="Registro de cortes"
          >
            <FaCut />
          </NavLink>
        </nav>
      </div>

      <div className="sidebar-rodape">
        <hr className="sidebar-divisor" />

        <NavLink
          to="/perfil"
          className={criarClasseDoLink}
          title="Meu perfil"
        >
          <FaUser />
        </NavLink>

        <NavLink
          to="/configuracoes"
          className={criarClasseDoLink}
          title="Configurações"
        >
          <FaCog />
        </NavLink>

        <button
          className="sidebar-link sidebar-botao botao-sair"
          title="Sair"
          onClick={handleLogout}
        >
          <FaSignOutAlt />
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;