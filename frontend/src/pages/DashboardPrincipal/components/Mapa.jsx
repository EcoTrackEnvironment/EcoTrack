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

function Mapa() {
    const [dadosMapa, setDadosMapa] = useState(null);
    const [carregando, setCarregando] = useState(true);
    const [processando, setProcessando] = useState(false);
    const [dataProjecao, setDataProjecao] = useState("");
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

    useEffect(() => {
        const hoje = new Date();
        const daqui30 = new Date(hoje.getTime() + 30 * 86400000);
        const dataInicial = daqui30.toISOString().slice(0, 10);
        setDataProjecao(dataInicial);
        buscarDados(dataInicial);
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
                                                
                                                <Polyline 
                                                    positions={[...dadosMapa.rota, dadosMapa.rota[0]]} 
                                                    color="#0c3260" 
                                                    weight={3} 
                                                    opacity={0.3} 
                                                    dashArray="6 6"
                                                />

                                                {dadosMapa.celulas.map((c, idx) => (
                                                    <Circle 
                                                        key={idx}
                                                        center={[c.latitude, c.longitude]}
                                                        radius={c.raio_metros}
                                                        pathOptions={{ 
                                                            color: mapaCores[c.cor], 
                                                            fillColor: mapaCores[c.cor],
                                                            fillOpacity: 0.8,
                                                            weight: 1
                                                        }}
                                                    >
                                                        <Popup>
                                                            <div className="custom-popup">
                                                                <strong>{c.altura_cm.toFixed(1)} cm</strong> — <strong style={{ color: mapaCores[c.cor] }}>{c.cor}</strong><br/>
                                                                {c.especie}<br/>
                                                                {c.dias_desde_corte} dias desde o corte<br/>
                                                                Confiança {(c.confianca * 100).toFixed(0)}%
                                                            </div>
                                                        </Popup>
                                                    </Circle>
                                                ))}
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
                                        <span className="chip">Projeção: {dadosMapa.dias_desde_corte} dias sem corte</span>
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