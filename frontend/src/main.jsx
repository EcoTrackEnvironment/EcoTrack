import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import DashboardLayout from "./layout/DashboardLayout";
import HomePrincipal from "./pages/DashboardPrincipal";
import DashboardVegetacao from "./pages/DashboardIndicadoresAmbientais";
import RegistroCortes from "./pages/RegistroCortes";
import Login from "./pages/Login/Login";
import MeuPerfil from "./pages/MeuPerfil/MeuPerfil";
import Configuracoes from "./pages/Configuracoes/Configuracoes";

import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />

        <Route element={<DashboardLayout />}>
          <Route
            path="/dashboard"
            element={<HomePrincipal />}
          />

          <Route
            path="/indicadores-ambientais"
            element={<DashboardVegetacao />}
          />

          <Route
            path="/registro-cortes"
            element={<RegistroCortes />}
          />

          <Route
          path="/perfil" element={<MeuPerfil />}
          />

          <Route 
          path="/configuracoes" element={<Configuracoes />} 
          />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>
);