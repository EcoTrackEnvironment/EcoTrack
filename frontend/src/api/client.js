export const API_BASE_URL = (import.meta.env.VITE_ECOTRACK_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export function dataLocalISO(deslocamentoDias = 0) {
  const data = new Date();
  data.setDate(data.getDate() + deslocamentoDias);
  const ano = data.getFullYear();
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  const dia = String(data.getDate()).padStart(2, "0");
  return `${ano}-${mes}-${dia}`;
}
