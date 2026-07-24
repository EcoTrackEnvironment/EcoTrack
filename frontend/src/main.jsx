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
import DashboardVegetacao from "./pages/DashboardIndicadoresAmbientais"

import "./index.css";


createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<DashboardLayout />}>
          <Route
            index
            element={<Navigate to="/dashboard" replace />}
          />

          <Route
            path="/dashboard"
            element={<HomePrincipal/>}
          />

          <Route
            path="/indicadores-ambientais"
            element={<DashboardVegetacao/>}
          />
          
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>
);