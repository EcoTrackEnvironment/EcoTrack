import TituloCards from "./TituloCards"
import "../styles/EsqueletoCards.css"
import { FaMapLocationDot } from "react-icons/fa6";

function Mapa () {
    return(
        <div className="container-principal">
            <TituloCards icone={<FaMapLocationDot color="#0c3260" size={20} fontWeight={600}/>} texto={"Mapa da Rodovia - COLOCAR NOME DA RODOVIA"}/>
        </div>
    )
}

export default Mapa