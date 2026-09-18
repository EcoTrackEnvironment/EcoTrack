import { useState, useEffect } from "react";
import axios from "axios";

// Puxando os componentes do Dashboard Principal
import VariavelCard from "../DashboardPrincipal/components/VariaveisCards";
import TituloCards from "../DashboardPrincipal/components/TituloCards";

// Importando o novo componente de gráfico da sua pasta local
import GraficoLinha from "./components/GraficoLinha";

import { WiHumidity } from "react-icons/wi";
import { FaThermometerHalf, FaRegCalendarAlt, FaChartLine, FaLeaf } from "react-icons/fa";
import { API_BASE_URL } from "../../api/client";

// Puxando os estilos globais
import "../DashboardPrincipal/styles/EsqueletoCards.css";
import "../DashboardPrincipal/styles/VariaveisAnalisadas.css"; 
import "./index.css";

function DashboardVegetacao() {
  const [dados, setDados] = useState(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);

  const obterEstacaoAno = (dataString) => {
    if (!dataString) return "Desconhecida";
    const mes = new Date(dataString).getMonth() + 1;
    if (mes >= 3 && mes <= 5) return "Outono";
    if (mes >= 6 && mes <= 8) return "Inverno";
    if (mes >= 9 && mes <= 11) return "Primavera";
    return "Verão";
  };

  useEffect(() => {
    axios.get(`${API_BASE_URL}/variaveis-x`, {
      params: {
        latitude: -23.55,
        longitude: -46.63,
        especie: "Brachiaria (Urochloa)",
        dias_desde_corte: 30,
        raio_metros: 500
      }
    })
    .then(res => {
        setDados(res.data);
        setErro(null);
        setCarregando(false);
    })
    .catch(err => {
        console.error("Erro ao buscar indicadores", err);
        setErro(err.response?.data?.detail || err.message || "Dados indisponíveis.");
        setCarregando(false);
    });
  }, []);

  if (carregando) {
      return (
        <div className="container-principal">
           <TituloCards icone={<FaLeaf color="#0c3260" size={20} />} texto="Indicadores Ambientais" />
           <div className="loading-indicadores">Buscando dados climáticos...</div>
        </div>
      );
  }

  if (erro || !dados) {
      return (
        <div className="container-principal">
          <TituloCards icone={<FaLeaf color="#0c3260" size={20} />} texto="Indicadores Ambientais" />
          <div className="loading-indicadores">Indicadores indisponíveis: {typeof erro === "string" ? erro : "não foi possível carregar os dados operacionais."}</div>
        </div>
      );
  }

  return (
    <div className="container-principal">
      <TituloCards 
        icone={<FaLeaf color="#0c3260" size={20} />} 
        texto="Indicadores Ambientais e Vegetação" 
      />

      <div className="conteudo-indicadores">
        <p className="subtitulo-indicadores">
          Acompanhe as condições climáticas locais e o desenvolvimento projetado da vegetação.
        </p>
        
        <div className="container-variaveis layout-indicadores">
          <VariavelCard 
            icone={<WiHumidity color="#22ca00" size={28} />} 
            titulo="Umidade Estimada" 
            valorDaVariavel={`${dados.clima.umidade_pct}%`}
            descricao="Média da janela climática consultada"
          />

          <VariavelCard 
            icone={<FaThermometerHalf color="#aa0707" size={20} />} 
            titulo="Temperatura" 
            valorDaVariavel={`${dados.clima.temperatura_c}°C`}
            descricao="Média da janela climática consultada"
          />

          <VariavelCard 
            icone={<FaRegCalendarAlt color="#f8d616" size={20} />} 
            titulo="Estação do Ano" 
            valorDaVariavel={obterEstacaoAno(dados.data)}
            descricao="Ciclo climático" 
          />

          <VariavelCard 
            icone={<FaChartLine color="#0c3260" size={20} />} 
            titulo="Crescimento" 
            valorDaVariavel={`${dados.previsao.altura.toFixed(1)} cm`}
            descricao={`Confiança da previsão: ${(dados.previsao.probabilidade * 100).toFixed(0)}%`}
          />
        </div>

        {/* O novo componente de gráfico é injetado aqui */}
        <GraficoLinha />
        
      </div>
    </div>
  );
}

export default DashboardVegetacao;
