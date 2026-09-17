import "../styles/ListaPontosCriticos.css";
import { FaExclamationTriangle, FaExclamationCircle, FaMapMarkerAlt } from "react-icons/fa";

const rotuloStatus = {
    vermelho: "Crítico",
    amarelo: "Em Atenção",
};

// Lista os trechos que precisam de corte, dos mais críticos para os menos
// críticos. Vem direto das células reais da última varredura do mapa (mesmo
// dado que colore os círculos) -- passar o mouse num card mostra um balão
// resumido no ponto correspondente do mapa, e clicar seleciona a célula (que
// já abre o balão completo, com todas as espécies) -- celulaSelecionada e
// celulaEmHover são levantados até o HomePrincipal.
function ListaPontosCriticos({ celulasMapa, celulaSelecionada, onSelecionarCelula, onHoverCelula }) {
    if (!celulasMapa || celulasMapa.length === 0) {
        return (
            <div className="container-lista-pontos-criticos">
                <p className="lista-pontos-vazio">Aguardando a varredura do mapa...</p>
            </div>
        );
    }

    const pontos = celulasMapa
        .filter((c) => c.cor !== "verde")
        .sort((a, b) => b.altura_cm - a.altura_cm);

    if (pontos.length === 0) {
        return (
            <div className="container-lista-pontos-criticos">
                <p className="lista-pontos-vazio">Nenhum trecho em atenção ou crítico na via — tudo dentro do padrão.</p>
            </div>
        );
    }

    return (
        <div className="container-lista-pontos-criticos">
            <h4 className="titulo-secao-pontos-criticos">
                Trechos por criticidade ({pontos.length})
            </h4>

            <div className="lista-pontos-criticos">
                {pontos.map((ponto) => {
                    const selecionado =
                        celulaSelecionada &&
                        celulaSelecionada.latitude === ponto.latitude &&
                        celulaSelecionada.longitude === ponto.longitude;

                    return (
                        <button
                            type="button"
                            key={`${ponto.latitude},${ponto.longitude}`}
                            className={`card-ponto-critico card-ponto-${ponto.cor} ${selecionado ? "selecionado" : ""}`}
                            onMouseEnter={() => onHoverCelula?.(ponto)}
                            onMouseLeave={() => onHoverCelula?.(null)}
                            onFocus={() => onHoverCelula?.(ponto)}
                            onBlur={() => onHoverCelula?.(null)}
                            onClick={() => {
                                onSelecionarCelula?.(ponto);
                                // O balão completo assume o lugar do resumido.
                                onHoverCelula?.(null);
                            }}
                        >
                            <div className="card-ponto-cabecalho">
                                <span className="card-ponto-km">
                                    <FaMapMarkerAlt className="icone-km" />
                                    Km {ponto.posicaoKm ?? "—"}
                                </span>
                                <span className={`selo-status selo-${ponto.cor}`}>
                                    {ponto.cor === "vermelho" ? <FaExclamationTriangle /> : <FaExclamationCircle />}
                                    {rotuloStatus[ponto.cor]}
                                </span>
                            </div>

                            <div className="card-ponto-altura">
                                {ponto.altura_cm.toFixed(1)} cm
                                <span className="card-ponto-especie">— {ponto.especie} (mais alta)</span>
                            </div>

                            <div className="card-ponto-detalhes">
                                <span>{ponto.dias_desde_corte} dias sem corte</span>
                                <span>Confiança {(ponto.confianca * 100).toFixed(0)}%</span>
                            </div>

                            {selecionado && (
                                <div className="card-ponto-selecionado-aviso">Em foco no mapa</div>
                            )}
                        </button>
                    );
                })}
            </div>
        </div>
    );
}

export default ListaPontosCriticos;
