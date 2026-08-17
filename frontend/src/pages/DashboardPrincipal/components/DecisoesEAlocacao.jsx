import { useState } from "react";
import TituloCards from "./TituloCards";
import "../styles/EsqueletoCards.css";
import "../styles/DecisoesEAlocacao.css"; 
import { FaBrain } from "react-icons/fa";
import RecomendacaoSistema from "./CardRecomendacaoSistema";
import { MdMapsUgc } from "react-icons/md";
import EquipesDisponiveis from "./EquipesDisponiveis";
import OperacaoManual from "./OperacaoManual";

function DecisoesEAlocacao() {
    const [abaAtiva, setAbaAtiva] = useState("automatico");

    return (
        <div className="container-principal">
            <TituloCards 
                icone={<FaBrain color="#0c3260" size={20} />} 
                texto={"Central de Decisões e Alocação"} 
            />

            <div className="container-abas">
                <button
                    className={`botao-aba ${abaAtiva === "automatico" ? "ativo" : ""}`}
                    onClick={() => setAbaAtiva("automatico")}
                >
                    Automático
                </button>
                <button
                    className={`botao-aba ${abaAtiva === "manual" ? "ativo" : ""}`}
                    onClick={() => setAbaAtiva("manual")}
                >
                    Manual
                </button>
            </div>

            <div className="conteudo-aba">
                {/* A renderização do conteúdo muda baseada no estado */}
                {abaAtiva === "automatico" && 
                    <div className="conteudo-automatico">
                        <div className="recomendacao">
                            <RecomendacaoSistema icone={<MdMapsUgc/>} titulo={"Recomendação do Sistema"} qtd_trechos_criticos={"Foram detectados 3 trechos críticos"} descricao_recomendacao={"Alocar Equipe Delta (Km 160) para RodoAnel Km 170 (risco de multa imediata)"}/>
                        </div>

                        <EquipesDisponiveis/>
                    </div>
                }
                {abaAtiva === "manual" && <OperacaoManual/>}
            </div>
        </div>
    );
}

export default DecisoesEAlocacao;