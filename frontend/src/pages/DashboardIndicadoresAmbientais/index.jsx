import { useState, useEffect } from "react";
import axios from "axios";

import VariavelCard from "../DashboardPrincipal/components/VariaveisCards";
import TituloCards from "../DashboardPrincipal/components/TituloCards";

import { WiHumidity } from "react-icons/wi";
import { FaThermometerHalf, FaRegCalendarAlt, FaChartLine, FaLeaf } from "react-icons/fa";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

import "../DashboardPrincipal/styles/EsqueletoCards.css";
import "../DashboardPrincipal/styles/VariaveisAnalisadas.css"; 

// Mantém o CSS local da tela de indicadores
import "./index.css";

function DashboardVegetacao() {
  const [dados, setDados] = useState(null);
  const [carregando, setCarregando] = useState(true);

  // Deriva a estação do ano a partir da data da previsão
  const obterEstacaoAno = (dataString) => {
    if (!dataString) return "Desconhecida";
    const mes = new Date(dataString).getMonth() + 1;
    if (mes >= 3 && mes <= 5) return "Outono";
    if (mes >= 6 && mes <= 8) return "Inverno";
    if (mes >= 9 && mes <= 11) return "Primavera";
    return "Verão";
  };

  useEffect(() => {
    axios.get("http://127.0.0.1:8000/variaveis-x", {
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
        setCarregando(false);
    })
    .catch(err => {
        console.error("Erro ao buscar indicadores", err);
        setCarregando(false);
    });
  }, []);

  const alturaFinal = dados?.previsao?.altura || 0;
  const dadosGrafico = [
    { dia: "Dia 0", altura: 0 },
    { dia: "Dia 7", altura: alturaFinal * 0.12 },
    { dia: "Dia 14", altura: alturaFinal * 0.38 },
    { dia: "Dia 21", altura: alturaFinal * 0.72 },
    { dia: "Dia 30", altura: alturaFinal },
  ];

  if (carregando) {
      return (
        <div className="container-principal">
           <TituloCards icone={<FaLeaf color="#0c3260" size={20} />} texto="Indicadores Ambientais" />
           <div className="loading-indicadores">Buscando dados climáticos...</div>
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
            valorDaVariavel={`${dados?.clima?.umidade_pct || 0}%`} 
            descricao="Média diária atual" 
          />

          <VariavelCard 
            icone={<FaThermometerHalf color="#aa0707" size={20} />} 
            titulo="Temperatura" 
            valorDaVariavel={`${dados?.clima?.temperatura_c || 0}°C`} 
            descricao="Clima da região monitorada" 
          />

          <VariavelCard 
            icone={<FaRegCalendarAlt color="#f8d616" size={20} />} 
            titulo="Estação do Ano" 
            valorDaVariavel={obterEstacaoAno(dados?.data)} 
            descricao="Ciclo climático" 
          />

          <VariavelCard 
            icone={<FaChartLine color="#0c3260" size={20} />} 
            titulo="Crescimento" 
            valorDaVariavel={`${alturaFinal.toFixed(1)} cm`} 
            descricao={`Confiança da IA: ${(dados?.previsao?.probabilidade * 100).toFixed(0)}%`} 
          />
        </div>

        {/* Seção do Gráfico */}
        <div className="grafico-container">
            <h3 className="titulo-grafico">Projeção de Crescimento da Vegetação (Janela de 30 dias)</h3>
            <div className="grafico-wrapper">
              <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={dadosGrafico} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#dcdde1" />
                      <XAxis dataKey="dia" axisLine={false} tickLine={false} tick={{fill: '#7f8c8d', fontSize: 12}} dy={10} />
                      <YAxis axisLine={false} tickLine={false} tick={{fill: '#7f8c8d', fontSize: 12}} dx={-10} unit="cm" />
                      <Tooltip 
                          contentStyle={{ borderRadius: '8px', border: '1px solid #dcdde1', boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}
                          itemStyle={{ color: '#0c3260', fontWeight: 'bold' }}
                      />
                      <Line 
                          type="monotone" 
                          dataKey="altura" 
                          stroke="#0c3260" 
                          strokeWidth={3}
                          dot={{ r: 4, fill: '#0c3260', strokeWidth: 2, stroke: '#fff' }} 
                          activeDot={{ r: 6 }} 
                          name="Altura (cm)"
                      />
                  </LineChart>
              </ResponsiveContainer>
            </div>
        </div>
      </div>
    </div>
  );
}

export default DashboardVegetacao;