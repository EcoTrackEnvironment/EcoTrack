import { useState, useEffect } from "react";
import axios from "axios";
import { MapContainer, TileLayer, Polyline, Circle, Popup, useMap } from "react-leaflet";
import TituloCards from "./TituloCards";
import { FaMapLocationDot } from "react-icons/fa6";
import "leaflet/dist/leaflet.css";
import "../styles/EsqueletoCards.css";
import "../styles/Mapa.css";

const mapaCores = {
    "verde": "#22ca00",
    "amarelo": "#f8d616",
    "vermelho": "#aa0707"
};

// Mesmos limiares do backend (config.classificar_cor). As cinco espécies
// convivem em todo trecho: o mapa é colorido pela mais alta de cada ponto
// (critério de disparo da roçada) e o popup usa isto para colorir as demais.
function classificarCor(alturaCm) {
    if (alturaCm > 25) return "vermelho";
    if (alturaCm > 15) return "amarelo";
    return "verde";
}

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

function Mapa({ celulaSelecionada, onSelecionarCelula }) {
    const [dadosMapa, setDadosMapa] = useState(null);
    const [carregando, setCarregando] = useState(true);
    const [processando, setProcessando] = useState(false);
    // Abre em HOJE: com os cortes registrados no banco, esta é a foto real da
    // via. Projeção para frente continua a um clique, mudando a data.
    const [dataProjecao, setDataProjecao] = useState(() =>
        new Date().toISOString().slice(0, 10)
    );
    const [erro, setErro] = useState(null);
    const [nomeRodovia, setNomeRodovia] = useState("");

    const buscarDados = async (data) => {
        setProcessando(true);
        setErro(null);
        try {
            const query = data ? `?data=${data}` : "";
            const resposta = await axios.get(`http://127.0.0.1:8000/mapa/rodovia${query}`);
            const respostaNomeRodovia = await axios.get("http://127.0.0.1:8000/");
            setDadosMapa(resposta.data);
            setNomeRodovia(respostaNomeRodovia.data.regiao);
        } catch (error) {
            console.error("ERRO na varredura: ", error);
            setErro(error.message);
        } finally {
            setCarregando(false);
            setProcessando(false);
        }
    };

    // Varredura inicial, só na montagem: depois quem dispara é o botão. Sai do
    // corpo do efeito porque `buscarDados` liga o estado de "processando" — e
    // de quebra o cleanup cancela a segunda montagem do StrictMode, evitando
    // varrer a rodovia duas vezes ao abrir a tela.
    useEffect(() => {
        const agendada = setTimeout(() => buscarDados(dataProjecao), 0);
        return () => clearTimeout(agendada);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);


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
                                <span className="item"><span className="sw verde"></span>0-10 cm</span>
                                <span className="item"><span className="sw amarelo"></span>11–30 cm</span>
                                <span className="item"><span className="sw vermelho"></span>&gt; 30 cm</span>
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
                                                    onSelecionar={onSelecionarCelula}
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
                                                    return (
                                                    <Circle
                                                        key={idx}
                                                        center={[c.latitude, c.longitude]}
                                                        radius={c.raio_metros}
                                                        eventHandlers={{ click: () => onSelecionarCelula?.(c) }}
                                                        pathOptions={{
                                                            // A célula em foco ganha um anel escuro; o preenchimento
                                                            // continua sendo a cor de status do trecho.
                                                            color: selecionada ? "#0c3260" : mapaCores[c.cor],
                                                            fillColor: mapaCores[c.cor],
                                                            fillOpacity: 0.8,
                                                            weight: selecionada ? 4 : 1
                                                        }}
                                                    >
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
                                                                        ? "Trecho em foco no gráfico de tendência"
                                                                        : "Clique para ver a tendência deste trecho"}
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
                                        <span className="chip"><span className="sw verde"></span>{dadosMapa.resumo.verde} Adequados</span>
                                        <span className="chip"><span className="sw amarelo"></span>{dadosMapa.resumo.amarelo} Em Atenção</span>
                                        <span className="chip"><span className="sw vermelho"></span>{dadosMapa.resumo.vermelho} Críticos</span>
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