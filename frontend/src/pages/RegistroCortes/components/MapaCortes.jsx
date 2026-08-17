// Mapa da tela de registro de cortes.
//
// É o mesmo mapa operacional da tela 1 (mesma varredura /mapa/rodovia, mesmas
// cores de status, mesma seleção por proximidade), com duas diferenças:
//   * o clique aqui não alimenta o gráfico, e sim o formulário de corte — ele
//     devolve a coordenada da célula escolhida;
//   * os cortes já registrados por ponto aparecem desenhados como anéis
//     tracejados, no raio de influência de cada um, para o operador ver o que
//     já está coberto antes de registrar mais um.
import { useState, useEffect } from "react";
import axios from "axios";
import { MapContainer, TileLayer, Polyline, Circle, CircleMarker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const API_BASE = "http://127.0.0.1:8000";

const mapaCores = {
    "verde": "#22ca00",
    "amarelo": "#f8d616",
    "vermelho": "#aa0707",
};

function AjusteDeCamera({ celulas }) {
    const map = useMap();
    useEffect(() => {
        if (celulas && celulas.length > 0) {
            const bounds = celulas.map((c) => [c.latitude, c.longitude]);
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

// No zoom em que a rodovia inteira cabe na tela cada célula tem uns 2 px:
// clicar em qualquer lugar seleciona a célula MAIS PRÓXIMA.
function SelecaoPorProximidade({ celulas, onSelecionar }) {
    const map = useMap();
    useEffect(() => {
        if (!celulas || celulas.length === 0) return;
        const aoClicar = (evento) => {
            if (evento.originalEvent?.target?.classList?.contains("leaflet-interactive")) return;
            const { lat, lng } = evento.latlng;
            let maisProxima = null;
            let menorDistancia = Infinity;
            for (const c of celulas) {
                const d = distanciaKm(lat, lng, c.latitude, c.longitude);
                if (d < menorDistancia) { menorDistancia = d; maisProxima = c; }
            }
            if (maisProxima && menorDistancia <= 3) onSelecionar?.(maisProxima);
        };
        map.on("click", aoClicar);
        return () => map.off("click", aoClicar);
    }, [map, celulas, onSelecionar]);
    return null;
}

function MapaCortes({ pontoSelecionado, onSelecionarPonto, cortes = [], versao = 0 }) {
    const [dadosMapa, setDadosMapa] = useState(null);
    const [erro, setErro] = useState(null);
    // Versão já buscada — comparar com a atual dá o estado de carregamento sem
    // precisar setar estado dentro do efeito.
    const [versaoResolvida, setVersaoResolvida] = useState(null);
    const carregando = versaoResolvida !== versao;

    // Sempre a foto de HOJE: aqui o operador registra o que já aconteceu no
    // campo, então projeção futura só atrapalharia a leitura.
    useEffect(() => {
        let cancelado = false;
        axios
            .get(`${API_BASE}/mapa/rodovia`)
            .then((resposta) => {
                if (cancelado) return;
                setDadosMapa(resposta.data);
                setErro(null);
            })
            .catch((error) => {
                if (cancelado) return;
                const detalhe = error.response?.data?.detail;
                setErro(typeof detalhe === "string" ? detalhe : error.message);
            })
            .finally(() => { if (!cancelado) setVersaoResolvida(versao); });
        return () => { cancelado = true; };
    }, [versao]);

    const cortesPontuais = cortes.filter((c) => c.escopo === "ponto");

    if (carregando) return <div className="cortes-mapa-status">Carregando o mapa da rodovia...</div>;
    if (erro) return <div className="cortes-mapa-status cortes-mapa-erro">Falha ao carregar o mapa: {erro}</div>;

    return (
        <div className="cortes-mapa-wrapper">
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
                            onSelecionar={onSelecionarPonto}
                        />

                        <Polyline
                            positions={[...dadosMapa.rota, dadosMapa.rota[0]]}
                            color="#0c3260"
                            weight={3}
                            opacity={0.3}
                            dashArray="6 6"
                        />

                        {/* Área já coberta por um corte registrado por ponto. */}
                        {cortesPontuais.map((corte) => (
                            <Circle
                                key={`corte-${corte.id}`}
                                center={[corte.latitude, corte.longitude]}
                                radius={corte.raio_influencia_m}
                                interactive={false}
                                pathOptions={{
                                    color: "#0c3260",
                                    fillColor: "#0c3260",
                                    fillOpacity: 0.06,
                                    weight: 1.5,
                                    dashArray: "5 5",
                                }}
                            />
                        ))}

                        {dadosMapa.celulas.map((c, idx) => (
                            <Circle
                                key={idx}
                                center={[c.latitude, c.longitude]}
                                radius={c.raio_metros}
                                eventHandlers={{ click: () => onSelecionarPonto?.(c) }}
                                pathOptions={{
                                    color: mapaCores[c.cor],
                                    fillColor: mapaCores[c.cor],
                                    fillOpacity: 0.8,
                                    weight: 1,
                                }}
                            >
                                <Popup>
                                    <div className="custom-popup">
                                        <strong>{c.altura_cm.toFixed(1)} cm</strong> — {c.especie}<br />
                                        Cortada em {c.corte?.data_corte} a {c.corte?.altura_corte_cm} cm<br />
                                        {c.dias_desde_corte} dias desde o corte
                                    </div>
                                </Popup>
                            </Circle>
                        ))}

                        {/* Ponto em foco no formulário. */}
                        {pontoSelecionado && (
                            <CircleMarker
                                center={[pontoSelecionado.latitude, pontoSelecionado.longitude]}
                                radius={9}
                                interactive={false}
                                pathOptions={{ color: "#0c3260", fillColor: "#ffffff", fillOpacity: 1, weight: 3 }}
                            />
                        )}
                    </>
                )}
            </MapContainer>
        </div>
    );
}

export default MapaCortes;
