import TituloCards from "./TituloCards"
import "../styles/EsqueletoCards.css"
import { FaChartLine } from "react-icons/fa6";

function GraficoLinha () {
    return(
        <div className="container-principal">
            <TituloCards icone={<FaChartLine color="#0c3260" size={20} fontWeight={600}/>} texto={"Tendência de Crescimento Estimado"}/>
        </div>
    )
}

export default GraficoLinha