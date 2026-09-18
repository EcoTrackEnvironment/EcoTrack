import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { MapContainer, TileLayer, Polyline, Circle, Popup, Tooltip, useMap } from "react-leaflet";
import TituloCards from "./TituloCards";
import { FaMapLocationDot } from "react-icons/fa6";
import "leaflet/dist/leaflet.css";
import { API_BASE_URL, dataLocalISO } from "../../../api/client";
import "../styles/EsqueletoCards.css";
import "../styles/Mapa.css";

const mapaCores = {
    "verde": "#22ca00",
    "amarelo": "#f8d616",
    "vermelho": "#aa0707"
};

// Espaçamento entre células usado na varredura do backend (src/mapa.py,
// gerar_mapa_rodovia). O front nunca envia esse parâmetro, então o padrão é
// sempre este valor -- usado aqui só para dar uma posição aproximada
// ("Km X") a cada célula, já que elas só trazem latitude/longitude.
const ESPACAMENTO_CELULA_KM = 0.2;

// Mesmos limiares do backend (config.classificar_cor). As cinco espécies
// convivem em todo trecho: o mapa é colorido pela mais alta de cada ponto
// (critério de disparo da roçada) e o popup usa isto para colorir as demais.
function classificarCor(alturaCm) {
    if (alturaCm > 25) return "vermelho";
    if (alturaCm > 15) return "amarelo";
    return "verde";
}

const rotuloStatus = {
    verde: "Adequado",
    amarelo: "Em Atenção",
    vermelho: "Crítico",
};

function formatarData(iso) {
    if (!iso) return "—";
    const [ano, mes, dia] = iso.split("-");
    return `${dia}/${mes}/${ano}`;
}

function AjusteDeCamera({ celulas }) {
    const map = useMap();
    useEffect(() => {
        if (celulas && celulas.length > 0) {
            const bounds = celulas.map(c => [c.latitude, c.longitude]);
            map.fitBounds(bounds, { padding: [24, 24] });
        }
    }, [celulas, map]);
    return null;
}

// Um clique direto numa bolinha já abre o popup dela sozinho (é o
// comportamento nativo do Leaflet). Mas quando a seleção vem de fora do mapa
// -- uma busca resolvida no card de Consulta -- nada dispara esse popup
// automaticamente; sem isso, o clique some sem nenhum feedback visual.
function AbrirPopupSelecionado({ celulaSelecionada, obterCamada }) {
    const map = useMap();
    useEffect(() => {
        if (!celulaSelecionada) return;
        const camada = obterCamada(celulaSelecionada.latitude, celulaSelecionada.longitude);
        if (!camada) return;
        map.closePopup();
        camada.openPopup();
        map.panTo([celulaSelecionada.latitude, celulaSelecionada.longitude]);
    }, [celulaSelecionada, map, obterCamada]);
    return null;
}

// Fechar o popup pelo X (ou clicando fora, longe de qualquer célula) deve
// limpar a seleção -- senão o card na lista continua marcado "Em foco no
// mapa" sem balão nenhum aberto. Só dá pra saber isso DEPOIS: o Leaflet
// dispara "popupclose" tanto nesse caso quanto quando TROCAMOS de seleção
// (o popup antigo fecha antes do novo abrir). Por isso o pequeno atraso: se
// nenhum popup novo tiver aberto até lá, foi um fechamento mesmo -- limpa.
function LimparSelecaoAoFecharPopup({ onSelecionarCelula }) {
    const map = useMap();
    useEffect(() => {
        const aoFechar = () => {
            // 300ms: dá tempo da animação de fechamento do Leaflet (~0.2s)
            // terminar e o popup antigo sumir do DOM antes de checar -- e,
            // se for troca de seleção, do novo já ter aberto.
            setTimeout(() => {
                const aindaTemPopupAberto = map.getContainer().querySelector(".leaflet-popup");
                if (!aindaTemPopupAberto) {
                    onSelecionarCelula?.(null);
                }
            }, 300);
        };
        map.on("popupclose", aoFechar);
        return () => map.off("popupclose", aoFechar);
    }, [map, onSelecionarCelula]);
    return null;
}

// Passar o mouse num card da lista de Pontos Críticos abre, no ponto
// correspondente do mapa, um balão RESUMIDO (Tooltip) -- diferente do balão
// completo (Popup), que só abre com clique/seleção. Fecha o balão anterior
// antes de abrir o novo, e some quando o mouse sai do card.
function BalaoResumoHover({ celulaEmHover, obterCamada }) {
    const camadaAbertaRef = useRef(null);
    useEffect(() => {
        if (camadaAbertaRef.current) {
            camadaAbertaRef.current.closeTooltip();
            camadaAbertaRef.current = null;
        }
        if (!celulaEmHover) return;
        const camada = obterCamada(celulaEmHover.latitude, celulaEmHover.longitude);
        if (!camada) return;
        camada.openTooltip();
        camadaAbertaRef.current = camada;
    }, [celulaEmHover, obterCamada]);
    return null;
}

// Distância aproximada em km entre dois pontos, na latitude da RMSP.
function distanciaKm(lat1, lon1, lat2, lon2) {
    const dLat = (lat2 - lat1) * 111.0;
    const dLon = (lon2 - lon1) * 111.32 * Math.cos((lat1 * Math.PI) / 180);
    return Math.hypot(dLat, dLon);
}

// No zoom em que a rodovia inteira cabe na tela, cada célula tem uns 2 px —
// ninguém acerta isso no clique. Então o alvo é o mapa: clicar em qualquer
// lugar seleciona a célula MAIS PRÓXIMA, e o operador só precisa chegar perto.
function SelecaoPorProximidade({ celulas, onSelecionar }) {
    const map = useMap();
    useEffect(() => {
        if (!celulas || celulas.length === 0) return;
        const aoClicar = (evento) => {
            // Clique em cima de uma célula já foi tratado pelo handler dela.
            if (evento.originalEvent?.target?.classList?.contains("leaflet-interactive")) return;
            const { lat, lng } = evento.latlng;
            let maisProxima = null;
            let menorDistancia = Infinity;
            for (const c of celulas) {
                const d = distanciaKm(lat, lng, c.latitude, c.longitude);
                if (d < menorDistancia) { menorDistancia = d; maisProxima = c; }
            }
            // Clique longe da via não seleciona nada (evita escolha aleatória).
            if (maisProxima && menorDistancia <= 3) onSelecionar?.(maisProxima);
        };
        map.on("click", aoClicar);
        return () => map.off("click", aoClicar);
    }, [map, celulas, onSelecionar]);
    return null;
}

function Mapa({ celulaSelecionada, onSelecionarCelula, onCelulasCarregadas, celulaEmHover }) {
    const [dadosMapa, setDadosMapa] = useState(null);
    const [carregando, setCarregando] = useState(true);
    const [processando, setProcessando] = useState(false);
    // Abre em HOJE: com os cortes registrados no banco, esta é a foto real da
    // via. Projeção para frente continua a um clique, mudando a data.
    const [dataProjecao, setDataProjecao] = useState(() =>
        dataLocalISO()
    );
    const [erro, setErro] = useState(null);
    const [nomeRodovia, setNomeRodovia] = useState("");
    // Cor em destaque pelos chips de status (verde/amarelo/vermelho) --
    // clicar num chip realça no mapa só as células daquele status.
    const [corEmDestaque, setCorEmDestaque] = useState(null);
    // Camadas Leaflet de cada célula, por coordenada — usado só para abrir o
    // popup programaticamente quando a seleção vem de fora do mapa.
    const camadasRef = useRef({});
    const requisicaoRef = useRef(0);
    const abortRef = useRef(null);
    const obterCamada = useCallback(
        (lat, lon) => camadasRef.current[`${lat},${lon}`],
        []
    );

    const buscarDados = async (data) => {
        abortRef.current?.abort();
        const controller = new AbortController();
        abortRef.current = controller;
        const requisicao = ++requisicaoRef.current;
        setProcessando(true);
        setErro(null);
        onCelulasCarregadas?.([]);
        onSelecionarCelula?.(null);
        try {
            const query = data ? `?data=${data}` : "";
            const resposta = await axios.get(`${API_BASE_URL}/mapa/rodovia${query}`, { signal: controller.signal });
            if (requisicao !== requisicaoRef.current) return;
            setDadosMapa(resposta.data);
            try {
                const respostaNomeRodovia = await axios.get(`${API_BASE_URL}/`, { signal: controller.signal });
                if (requisicao === requisicaoRef.current) {
                    setNomeRodovia(respostaNomeRodovia.data.regiao || "");
                }
            } catch (errorNome) {
                if (!controller.signal.aborted) console.warn("Não foi possível carregar o nome da rodovia.", errorNome);
            }
        } catch (error) {
            if (controller.signal.aborted || requisicao !== requisicaoRef.current) return;
            console.error("ERRO na varredura: ", error);
            setErro(error.message);
            setDadosMapa(null);
            onCelulasCarregadas?.([]);
            onSelecionarCelula?.(null);
        } finally {
            if (requisicao === requisicaoRef.current) {
                setCarregando(false);
                setProcessando(false);
            }
        }
    };

    // Varredura inicial, só na montagem: depois quem dispara é o botão. Sai do
    // corpo do efeito porque `buscarDados` liga o estado de "processando" — e
    // de quebra o cleanup cancela a segunda montagem do StrictMode, evitando
    // varrer a rodovia duas vezes ao abrir a tela.
    useEffect(() => {
        const agendada = setTimeout(() => buscarDados(dataProjecao), 0);
        return () => {
            clearTimeout(agendada);
            abortRef.current?.abort();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Repassa as células da varredura atual para quem estiver ouvindo (o
    // card de Consulta Específica de Trecho usa isso para achar a bolinha
    // mais próxima quando o operador pesquisa por lá, em vez de pelo mapa).
    useEffect(() => {
        if (dadosMapa) {
            onCelulasCarregadas?.(
                dadosMapa.celulas.map((c, idx) => ({
                    ...c,
                    dataAlvo: dadosMapa.data,
                    // Posição aproximada ao longo da rota (ordem da varredura
                    // x espaçamento entre células) -- não é o marco oficial
                    // da rodovia, mas dá uma referência de "Km" consistente
                    // entre o mapa e a Central de Decisões e Alocação.
                    posicaoKm: Math.round(idx * ESPACAMENTO_CELULA_KM * 10) / 10,
                }))
            );
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dadosMapa]);

    // Clicar num chip de status alterna o realce; clicar de novo limpa.
    const alternarDestaqueCor = (cor) => {
        setCorEmDestaque((atual) => (atual === cor ? null : cor));
    };


    return (
        <div className="container-principal">
            <TituloCards 
                icone={<FaMapLocationDot color="#0c3260" size={20} fontWeight={600} />} 
                texto={`Mapa Operacional da Rodovia: ${nomeRodovia}`}
            />
            
            <div className="map-card">
                {carregando ? (
                    <div className="map-loading">Carregando mapa...</div>
                ) : (
                    <>
                        <div className="map-toolbar">
                            <button 
                                className="btn-sweep" 
                                onClick={() => buscarDados(dataProjecao)}
                                disabled={processando}
                            >
                                {processando ? "Varrendo a rodovia..." : `Gerar Projeção de Crescimento`}
                            </button>
                            
                            <div className="toolbar-group">
                                <label>Projetar até:</label>
                                <input
                                    type="date"
                                    className="input-date"
                                    value={dataProjecao}
                                    onChange={(e) => setDataProjecao(e.target.value)}
                                />
                            </div>

                            <span className="grow"></span>

                            <div className="legend">
                                <span className="item"><span className="sw verde"></span>1–15 cm</span>
                                <span className="item"><span className="sw amarelo"></span>16–25 cm</span>
                                <span className="item"><span className="sw vermelho"></span>&gt; 25 cm</span>
                            </div>
                        </div>

                        {erro ? (
                            <div className="map-error">Falha na varredura: {erro}</div>
                        ) : (
                            <>
                                <div className="map-container-wrapper">
                                    <MapContainer 
                                        center={[-23.55, -46.63]} 
                                        zoom={10} 
                                        style={{ width: "100%", height: "100%", zIndex: 0 }}
                                    >
                                        <TileLayer
                                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                                        />
                                        
                                        {dadosMapa && (
                                            <>
                                                <AjusteDeCamera celulas={dadosMapa.celulas} />
                                                <SelecaoPorProximidade
                                                    celulas={dadosMapa.celulas}
                                                    onSelecionar={(c) => onSelecionarCelula?.({ ...c, dataAlvo: dadosMapa.data })}
                                                />
                                                <AbrirPopupSelecionado
                                                    celulaSelecionada={celulaSelecionada}
                                                    obterCamada={obterCamada}
                                                />
                                                <LimparSelecaoAoFecharPopup
                                                    onSelecionarCelula={onSelecionarCelula}
                                                />
                                                <BalaoResumoHover
                                                    celulaEmHover={celulaEmHover}
                                                    obterCamada={obterCamada}
                                                />

                                                <Polyline
                                                    positions={[...dadosMapa.rota, dadosMapa.rota[0]]}
                                                    color="#0c3260"
                                                    weight={3}
                                                    opacity={0.3}
                                                    dashArray="6 6"
                                                />

                                                {dadosMapa.celulas.map((c, idx) => {
                                                    const selecionada =
                                                        celulaSelecionada &&
                                                        celulaSelecionada.latitude === c.latitude &&
                                                        celulaSelecionada.longitude === c.longitude;
                                                    const destacada = corEmDestaque && c.cor === corEmDestaque;
                                                    const apagada = corEmDestaque && c.cor !== corEmDestaque;
                                                    const posicaoKm = Math.round(idx * ESPACAMENTO_CELULA_KM * 10) / 10;
                                                    return (
                                                    <Circle
                                                        key={idx}
                                                        ref={(camada) => {
                                                            if (camada) camadasRef.current[`${c.latitude},${c.longitude}`] = camada;
                                                        }}
                                                        center={[c.latitude, c.longitude]}
                                                        radius={destacada ? c.raio_metros * 1.8 : c.raio_metros}
                                                        eventHandlers={{ click: () => onSelecionarCelula?.({ ...c, dataAlvo: dadosMapa.data }) }}
                                                        pathOptions={{
                                                            // A célula em foco ganha um anel escuro; o preenchimento
                                                            // continua sendo a cor de status do trecho. Com um chip
                                                            // de status em destaque, as demais células apagam.
                                                            color: selecionada ? "#0c3260" : mapaCores[c.cor],
                                                            fillColor: mapaCores[c.cor],
                                                            fillOpacity: apagada ? 0.12 : 0.85,
                                                            opacity: apagada ? 0.25 : 1,
                                                            weight: selecionada ? 4 : destacada ? 3 : 1
                                                        }}
                                                    >
                                                        <Tooltip direction="top" offset={[0, -6]} className="tooltip-resumo">
                                                            <div className="tooltip-resumo-conteudo">
                                                                <strong>Km {posicaoKm}</strong>
                                                                <span>{c.altura_cm.toFixed(1)} cm</span>
                                                                <span className={`tooltip-selo tooltip-${c.cor}`}>{rotuloStatus[c.cor]}</span>
                                                            </div>
                                                        </Tooltip>
                                                        <Popup>
                                                            <div className="custom-popup">
                                                                <strong>{c.altura_cm.toFixed(1)} cm</strong> — <strong style={{ color: mapaCores[c.cor] }}>{c.cor}</strong><br/>
                                                                {c.especie} (mais alta)<br/>
                                                                {c.dias_desde_corte} dias desde o corte<br/>
                                                                {c.corte && (
                                                                    <>Cortada em {formatarData(c.corte.data_corte)} a {c.corte.altura_corte_cm} cm<br/></>
                                                                )}
                                                                Confiança {(c.confianca * 100).toFixed(0)}%
                                                                {c.alturas_por_especie && (
                                                                    <>
                                                                        <hr className="popup-sep" />
                                                                        <span className="popup-titulo">Todas as espécies no ponto</span>
                                                                        <table className="popup-especies">
                                                                            <tbody>
                                                                                {Object.entries(c.alturas_por_especie)
                                                                                    .sort((a, b) => b[1] - a[1])
                                                                                    .map(([nome, altura]) => (
                                                                                        <tr key={nome} className={nome === c.especie ? "ativa" : ""}>
                                                                                            <td><span className={`sw ${classificarCor(altura)}`}></span>{nome}</td>
                                                                                            <td>{altura.toFixed(1)} cm</td>
                                                                                        </tr>
                                                                                    ))}
                                                                            </tbody>
                                                                        </table>
                                                                    </>
                                                                )}
                                                                <div className="popup-selecao">
                                                                    {selecionada
                                                                        ? "Trecho em foco na Consulta Específica de Trecho"
                                                                        : "Clique para ver os detalhes deste trecho"}
                                                                </div>
                                                            </div>
                                                        </Popup>
                                                    </Circle>
                                                    );
                                                })}
                                            </>
                                        )}
                                    </MapContainer>
                                </div>

                                {dadosMapa && (
                                    <div className="map-summary">
                                        <span className="summary-label">Status da Via:</span>
                                        <button
                                            type="button"
                                            className={`chip chip-clicavel ${corEmDestaque === "verde" ? "chip-ativo" : ""}`}
                                            onClick={() => alternarDestaqueCor("verde")}
                                            title="Clique para destacar estes pontos no mapa"
                                        >
                                            <span className="sw verde"></span>{dadosMapa.resumo.verde} Adequados
                                        </button>
                                        <button
                                            type="button"
                                            className={`chip chip-clicavel ${corEmDestaque === "amarelo" ? "chip-ativo" : ""}`}
                                            onClick={() => alternarDestaqueCor("amarelo")}
                                            title="Clique para destacar estes pontos no mapa"
                                        >
                                            <span className="sw amarelo"></span>{dadosMapa.resumo.amarelo} Em Atenção
                                        </button>
                                        <button
                                            type="button"
                                            className={`chip chip-clicavel ${corEmDestaque === "vermelho" ? "chip-ativo" : ""}`}
                                            onClick={() => alternarDestaqueCor("vermelho")}
                                            title="Clique para destacar estes pontos no mapa"
                                        >
                                            <span className="sw vermelho"></span>{dadosMapa.resumo.vermelho} Críticos
                                        </button>
                                        {corEmDestaque && (
                                            <button type="button" className="chip chip-limpar" onClick={() => setCorEmDestaque(null)}>
                                                Limpar destaque
                                            </button>
                                        )}
                                        <span className="chip">Confiança Média: {(dadosMapa.confianca_media * 100).toFixed(0)}%</span>
                                        <span className="chip">
                                            {dadosMapa.dias_desde_corte_min === dadosMapa.dias_desde_corte
                                                ? `${dadosMapa.dias_desde_corte} dias desde o corte`
                                                : `${dadosMapa.dias_desde_corte_min}–${dadosMapa.dias_desde_corte} dias desde o corte`}
                                        </span>
                                        <span className="chip chip-especie">Pior caso entre as 5 espécies</span>
                                    </div>
                                )}
                            </>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}

export default Mapa;
