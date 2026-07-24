import "./index.css";
import VariavelCard from "./components/VariaveisCards";

import { WiHumidity } from "react-icons/wi";
import { FaThermometerHalf, FaRegCalendarAlt, FaChartLine } from "react-icons/fa";

function DashboardVegetacao() {
  return (
    <div className="dashboard">
      <h1 className="titulo">Indicadores Ambientais</h1>
      <p className="subtitulo">
        Acompanhe as condições do solo e o desenvolvimento da vegetação.
      </p>

      <div className="cards">

        <VariavelCard 
          icone={<WiHumidity color="#0c3260" size={24} />} 
          titulo="Umidade do Solo" 
          valorDaVariavel="42%" 
          descricao="Nível ideal para a vegetação atual" 
        />

        <VariavelCard 
          icone={<FaThermometerHalf color="#0c3260" size={20} />} 
          titulo="Temperatura" 
          valorDaVariavel="26°C" 
          descricao="Estável nas últimas 3 horas" 
        />

        <VariavelCard 
          icone={<FaRegCalendarAlt color="#0c3260" size={20} />} 
          titulo="Estação do Ano" 
          valorDaVariavel="Outono" 
          descricao="Período de transição climática" 
        />

        <VariavelCard 
          icone={<FaChartLine color="#0c3260" size={20} />} 
          titulo="Previsão do Crescimento" 
          valorDaVariavel="+15%" 
          descricao="Estimado para as próximas 2 semanas" 
        />

      </div>
    </div>
  );
}

export default DashboardVegetacao;