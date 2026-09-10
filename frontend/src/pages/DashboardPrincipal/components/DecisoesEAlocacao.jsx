import { useState } from "react";
import TituloCards from "./TituloCards";
import "../styles/EsqueletoCards.css";
import "../styles/DecisoesEAlocacao.css";
import { FaBrain } from "react-icons/fa";
import RecomendacaoSistema from "./CardRecomendacaoSistema";
import { MdMapsUgc } from "react-icons/md";
import EquipesDisponiveis from "./EquipesDisponiveis";
import ListaPontosCriticos from "./ListaPontosCriticos";

function DecisoesEAlocacao({ celulasMapa, celulaSelecionada, onSelecionarCelula, onHoverCelula }) {
    const [abaAtiva, setAbaAtiva] = useState("automatico");

    // Pontos que precisam de corte, do mais crítico para o menos crítico --
    // mesma célula real que colore o mapa, então a recomendação e a lista
    // batem sempre com o que está sendo exibido lá.
    const pontosCriticos = (celulasMapa || [])
        .filter((c) => c.cor !== "verde")
        .sort((a, b) => b.altura_cm - a.altura_cm);
    const pontoMaisCritico = pontosCriticos[0];

    const qtdTrechosTexto = celulasMapa && celulasMapa.length > 0
        ? pontosCriticos.length > 0
            ? `Foram detectados ${pontosCriticos.length} trecho${pontosCriticos.length > 1 ? "s" : ""} em atenção ou crítico`
            : "Nenhum trecho em atenção ou crítico na via"
        : "Aguardando a varredura do mapa...";

    const descricaoRecomendacao = pontoMaisCritico
        ? `Priorizar o trecho no Km ${pontoMaisCritico.posicaoKm} (${pontoMaisCritico.altura_cm.toFixed(1)} cm, ${pontoMaisCritico.cor === "vermelho" ? "crítico" : "em atenção"})`
        : "Nenhuma ação necessária no momento";

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
                    className={`botao-aba ${abaAtiva === "criticos" ? "ativo" : ""}`}
                    onClick={() => setAbaAtiva("criticos")}
                >
                    Pontos Críticos
                </button>
            </div>

            <div className="conteudo-aba">
                {/* A renderização do conteúdo muda baseada no estado */}
                {abaAtiva === "automatico" &&
                    <div className="conteudo-automatico">
                        <div className="recomendacao">
                            <RecomendacaoSistema
                                icone={<MdMapsUgc/>}
                                titulo={"Recomendação do Sistema"}
                                qtd_trechos_criticos={qtdTrechosTexto}
                                descricao_recomendacao={descricaoRecomendacao}
                                onClickAtivar={pontoMaisCritico ? () => onSelecionarCelula?.(pontoMaisCritico) : undefined}
                            />
                        </div>

                        <EquipesDisponiveis celulasMapa={celulasMapa} />
                    </div>
                }
                {abaAtiva === "criticos" &&
                    <ListaPontosCriticos
                        celulasMapa={celulasMapa}
                        celulaSelecionada={celulaSelecionada}
                        onSelecionarCelula={onSelecionarCelula}
                        onHoverCelula={onHoverCelula}
                    />
                }
            </div>
        </div>
    );
}

export default DecisoesEAlocacao;
