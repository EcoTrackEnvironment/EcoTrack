import { NavLink } from "react-router-dom";
import {
  FaChartPie,
  FaLeaf,
} from "react-icons/fa";

import "./Sidebar.css";

function Sidebar() {
  const criarClasseDoLink = ({ isActive }) => {
    return `sidebar-link ${isActive ? "ativo" : ""}`;
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        JS
      </div>

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
      </nav>
    </aside>
  );
}

export default Sidebar;