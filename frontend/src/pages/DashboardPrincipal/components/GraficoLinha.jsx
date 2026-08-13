import { useState, useEffect } from "react";
import axios from "axios";
import TituloCards from "./TituloCards";
import "../styles/EsqueletoCards.css";
import "../styles/GraficoLinha.css";
import { FaSearchLocation, FaMapMarkerAlt, FaInfoCircle } from "react-icons/fa";

const API_BASE = "http://127.0.0.1:8000";

// Fallback local, caso a API ainda nao tenha respondido (mesmos valores do config.py)
const CENTRO_REGIAO = { latitude: -23.55, longitude: -46.63 };
const ESPECIES_PADRAO = [
    "Brachiaria (Urochloa)",
    "Cynodon (grama-seda)",
    "Megathyrsus (capim-coloniao)",
    "Pennisetum (capim-elefante)",
    "Paspalum (grama-batatais)",
];

const DICA_DATA_FINAL =
    "É o último dia da janela de cálculo — o período considerado vai de \"dias desde o corte\" até esta data. Em branco, usa hoje.";

function GraficoLinha() {
    // Opcoes vindas da API
    const [pontos, setPontos] = useState([]);
    const [especies, setEspecies] = useState(ESPECIES_PADRAO);

    // Campos da consulta
    const [pontoSelecionado, setPontoSelecionado] = useState("manual");
    const [latitude, setLatitude] = useState(CENTRO_REGIAO.latitude);
    const [longitude, setLongitude] = useState(CENTRO_REGIAO.longitude);
    const [especieSelecionada, setEspecieSelecionada] = useState(ESPECIES_PADRAO[0]);

    // Podem ser usados juntos: "dias_desde_corte" define o tamanho da janela
    // e "data" define o dia final dela (fim = data, inicio = data - dias_desde_corte).
    const [diasDesdeCorte, setDiasDesdeCorte] = useState(30);
    const [dataFinal, setDataFinal] = useState("");

    // Estado da requisicao
    const [carregando, setCarregando] = useState(false);
    const [erro, setErro] = useState(null);
    const [resultado, setResultado] = useState(null);

    useEffect(() => {
        axios.get(`${API_BASE}/pontos`)
            .then((res) => setPontos(res.data?.pontos || []))
            .catch(() => {});

        axios.get(`${API_BASE}/especies`)
            .then((res) => {
                if (res.data?.especies?.length) {
                    setEspecies(res.data.especies);
                    setEspecieSelecionada(res.data.especies[0]);
                }
            })
            .catch(() => {});
    }, []);

    const lidarComSelecaoPonto = (valor) => {
        setPontoSelecionado(valor);
        if (valor === "manual") {
            setLatitude(CENTRO_REGIAO.latitude);
            setLongitude(CENTRO_REGIAO.longitude);
            return;
        }
        const ponto = pontos.find((p) => p.id === valor);
        if (ponto) {
            setLatitude(ponto.latitude);
            setLongitude(ponto.longitude);
        }
    };

    const lidarComEdicaoCoordenada = (setter) => (evento) => {
        setter(evento.target.value);
        setPontoSelecionado("manual"); // editar manualmente volta pro modo "coordenadas manuais"
    };

    const calcularAltura = async () => {
        setCarregando(true);
        setErro(null);
        try {
            const params = {
                latitude: Number(latitude),
                longitude: Number(longitude),
                especie: especieSelecionada,
                raio_metros: 500,
                dias_desde_corte: diasDesdeCorte,
            };
            if (dataFinal) {
                params.data = dataFinal;
            }

            const resposta = await axios.get(`${API_BASE}/variaveis-x`, { params });
            setResultado(resposta.data);
        } catch (error) {
            const detalhe = error.response?.data?.detail;
            const msg = typeof detalhe === "string"
                ? detalhe
                : detalhe?.erro || error.message || "Falha ao calcular a altura.";
            setErro(msg);
            setResultado(null);
        } finally {
            setCarregando(false);
        }
    };

    const consultaValida = latitude !== "" && longitude !== "" && !!especieSelecionada;

    return (
        <div className="container-principal">
            <TituloCards
                icone={<FaSearchLocation color="#0c3260" size={20} fontWeight={600} />}
                texto={"Consulta Específica de Trecho"}
            />

            <div className="consulta-trecho-corpo">
                {/* ---------- Painel esquerdo (40%): formulario ---------- */}
                <div className="painel-consulta">
                    <div className="grade-formulario">
                        <div className="campo-toolbar campo-full">
                            <label className="rotulo-campo">Ponto de monitoramento</label>
                            <select
                                className="select-consulta"
                                value={pontoSelecionado}
                                onChange={(e) => lidarComSelecaoPonto(e.target.value)}
                            >
                                <option value="manual">— Coordenadas manuais —</option>
                                {pontos.map((p) => (
                                    <option key={p.id} value={p.id}>
                                        {p.id} · {p.trecho}
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div className="campo-toolbar">
                            <label className="rotulo-campo">Coordenadas (lat, long)</label>
                            <div className="par-coordenadas">
                                <input
                                    type="number"
                                    step="0.01"
                                    aria-label="Latitude"
                                    className="input-consulta input-coord"
                                    value={latitude}
                                    onChange={lidarComEdicaoCoordenada(setLatitude)}
                                />
                                <span className="separador-coord">,</span>
                                <input
                                    type="number"
                                    step="0.01"
                                    aria-label="Longitude"
                                    className="input-consulta input-coord"
                                    value={longitude}
                                    onChange={lidarComEdicaoCoordenada(setLongitude)}
                                />
                            </div>
                        </div>

                        <div className="campo-toolbar">
                            <label className="rotulo-campo">Espécie de grama</label>
                            <select
                                className="select-consulta"
                                value={especieSelecionada}
                                onChange={(e) => setEspecieSelecionada(e.target.value)}
                            >
                                {especies.map((esp) => (
                                    <option key={esp} value={esp}>{esp}</option>
                                ))}
                            </select>
                        </div>

                        <div className="campo-toolbar">
                            <label className="rotulo-campo">
                                Dias desde o corte
                                <span className="valor-inline">{diasDesdeCorte}</span>
                            </label>
                            <input
                                type="range"
                                min="0"
                                max="365"
                                value={diasDesdeCorte}
                                className="input-range"
                                onChange={(e) => setDiasDesdeCorte(Number(e.target.value))}
                            />
                        </div>

                        <div className="campo-toolbar">
                            <label className="rotulo-campo">Data final (opcional)</label>
                            <input
                                type="date"
                                className="input-consulta"
                                value={dataFinal}
                                onChange={(e) => setDataFinal(e.target.value)}
                            />
                            <p className="dica-consulta" title={DICA_DATA_FINAL}>
                                <FaInfoCircle className="icone-dica" />
                                Fim da janela (padrão: hoje)
                            </p>
                        </div>

                        <div className="campo-toolbar campo-full">
                            <button
                                className="botao-calcular"
                                onClick={calcularAltura}
                                disabled={carregando || !consultaValida}
                            >
                                {carregando ? "Calculando..." : "Calcular altura"}
                            </button>
                        </div>
                    </div>
                </div>

                {/* ---------- Painel direito (60%): resultado em cards ---------- */}
                <div className="painel-resultado">
                    {erro ? (
                        <div className="consulta-erro">Falha na consulta: {erro}</div>
                    ) : !resultado ? (
                        <div className="consulta-vazio">
                            Preencha a consulta ao lado e clique em <strong>Calcular altura</strong>.
                        </div>
                    ) : (
                        <>
                            <div className="grade-principal-resultado">
                                <div className="metrica-card">
                                    <span className="metrica-rotulo">Altura estimada</span>
                                    <span className="metrica-valor">
                                        {resultado.previsao.altura.toFixed(1)} <small>cm</small>
                                    </span>
                                    <div className="barra-progresso">
                                        <div
                                            className="barra-preenchida"
                                            style={{ width: `${Math.min(100, (resultado.previsao.altura / 60) * 100)}%` }}
                                        />
                                    </div>
                                    <div className="barra-rotulos">
                                        <span>0</span><span>corte ≥ 30 cm</span><span>60</span>
                                    </div>
                                </div>

                                <div className="metrica-card">
                                    <span className="metrica-rotulo">Confiança</span>
                                    <span className="metrica-valor">
                                        {(resultado.previsao.probabilidade * 100).toFixed(1)}<small>%</small>
                                    </span>
                                    <div className="barra-progresso">
                                        <div
                                            className="barra-preenchida"
                                            style={{ width: `${resultado.previsao.probabilidade * 100}%` }}
                                        />
                                    </div>
                                    <div className="barra-rotulos">
                                        <span>0%</span><span>100%</span>
                                    </div>
                                </div>

                                <div className="metrica-card card-status">
                                    <div className={`selo-corte ${resultado.corte_recomendado ? "necessario" : "nao-necessario"}`}>
                                        <span className="ponto-selo" />
                                        {resultado.corte_recomendado ? "Corte necessário" : "Corte não necessário"}
                                    </div>
                                    <p className="linha-meta">
                                        {resultado.especie} · {resultado.dias_desde_corte}d · {resultado.data}
                                    </p>
                                    <p className="linha-meta">
                                        <FaMapMarkerAlt className="icone-local" />
                                        {resultado.localizacao.latitude.toFixed(2)}, {resultado.localizacao.longitude.toFixed(2)}
                                        {" "}(raio {resultado.localizacao.raio_metros} m)
                                    </p>
                                </div>
                            </div>

                            <div className="grade-clima">
                                <div className="chip-clima">
                                    <span className="chip-clima-titulo">
                                        <span className="swatch-clima" style={{ backgroundColor: "#aa0707" }} /> Temperatura
                                    </span>
                                    <span className="chip-clima-valor">{resultado.clima.temperatura_c}°C</span>
                                </div>
                                <div className="chip-clima">
                                    <span className="chip-clima-titulo">
                                        <span className="swatch-clima" style={{ backgroundColor: "#0712aa" }} /> Precipitação
                                    </span>
                                    <span className="chip-clima-valor">{resultado.clima.precipitacao_mm}mm</span>
                                </div>
                                <div className="chip-clima">
                                    <span className="chip-clima-titulo">
                                        <span className="swatch-clima" style={{ backgroundColor: "#22ca00" }} /> Umidade
                                    </span>
                                    <span className="chip-clima-valor">{resultado.clima.umidade_pct}%</span>
                                </div>
                                <div className="chip-clima">
                                    <span className="chip-clima-titulo">
                                        <span className="swatch-clima" style={{ backgroundColor: "#f8d616" }} /> Radiação
                                    </span>
                                    <span className="chip-clima-valor">{resultado.clima.radiacao_mj_m2}<small>MJ/m²</small></span>
                                </div>
                                <div className="chip-clima">
                                    <span className="chip-clima-titulo">
                                        <span className="swatch-clima" style={{ backgroundColor: "#7f8c8d" }} /> Vento
                                    </span>
                                    <span className="chip-clima-valor">{resultado.clima.vento_kmh}<small>km/h</small></span>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

export default GraficoLinha;