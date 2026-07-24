import "../styles/Exportacao.css";
import { FaShieldAlt, FaFilePdf, FaFileCsv, FaBuilding } from "react-icons/fa";

function Exportacao() {
    return (
        <div className="container-card-exportacao">
            
            <div className="titulo-exportacao">
                <FaShieldAlt className="icone-titulo-exportacao" />
                <span>Exportação e Conformidade</span>
            </div>
            
            <div className="botoes-exportacao">
                <button 
                    className="btn-exportacao btn-outline" 
                    onClick={() => console.log("Simulação: Gerando formulário PDF...")}
                >
                    <FaFilePdf className="icone-btn" />
                    Gerar Formulário Unifilar de Roçada (PDF)
                </button>
                
                <button 
                    className="btn-exportacao btn-outline" 
                    onClick={() => console.log("Simulação: Exportando CSV...")}
                >
                    <FaFileCsv className="icone-btn" />
                    Exportar Histórico (CSV)
                </button>
                
                <button 
                    className="btn-exportacao btn-filled" 
                    onClick={() => console.log("Simulação: Gerando Relatório ANTT/ARTESP...")}
                >
                    <FaBuilding className="icone-btn" />
                    Relatório de Compliance ANTT/ARTESP
                </button>
            </div>

        </div>
    );
}

export default Exportacao;