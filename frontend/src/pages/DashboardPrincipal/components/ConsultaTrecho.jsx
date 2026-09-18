// Card "Consulta Específica de Trecho" — trazido da branch frontend
// (commit fe2724e), onde ocupava o arquivo GraficoLinha.jsx. Aqui virou
// componente próprio para conviver com o gráfico de tendência.
//
// Integração com o mapa (adicionada depois): este card e o Mapa
// compartilham a "célula selecionada" através do HomePrincipal (index.jsx).
//   - Clique numa bolinha do mapa -> `celulaSelecionada` muda -> este card
//     preenche lat/long/dias/data sozinho e já calcula, usando a altura real
//     do corte registrado e a espécie "vencedora" daquele ponto (para o
//     resultado bater exatamente com o que o mapa mostra).
//   - Consulta manual por aqui permanece hipotética; o mapa destaca a célula
//     mais próxima sem substituir a resposta calculada.
import { useState, useEffect, useRef } from "react";
import axios from "axios";
import TituloCards from "./TituloCards";
import "../styles/EsqueletoCards.css";
import "../styles/ConsultaTrecho.css";
import { FaSearchLocation, FaMapMarkerAlt, FaInfoCircle } from "react-icons/fa";
import { API_BASE_URL } from "../../../api/client";

const API_BASE = API_BASE_URL;

// Fallback local, caso a API ainda nao tenha respondido (mesmos valores do config.py)
const CENTRO_REGIAO = { latitude: -23.55, longitude: -46.63 };

const DICA_DATA_FINAL =
    "É o último dia da janela de cálculo — o período considerado vai de \"dias desde o corte\" até esta data. Em branco, usa hoje.";

// Mesmos limiares/cores do mapa (config.classificar_cor / Mapa.jsx), para o
// selo de status e a tabela de espécies ficarem idênticos ao popup do mapa.
const CORES_STATUS = { verde: "#22ca00", amarelo: "#f8d616", vermelho: "#aa0707" };
const ROTULOS_STATUS = { verde: "Adequado", amarelo: "Em atenção", vermelho: "Crítico" };
const ESPECIES = [
    "Brachiaria (Urochloa)",
    "Cynodon (grama-seda)",
    "Megathyrsus (capim-coloniao)",
    "Pennisetum (capim-elefante)",
    "Paspalum (grama-batatais)",
];

function formatarData(iso) {
    if (!iso) return "—";
    const [ano, mes, dia] = iso.split("-");
    return `${dia}/${mes}/${ano}`;
}

function ConsultaTrecho({ celulaSelecionada, onConsultaResolvida }) {
    // Campos visíveis do formulário
    const [latitude, setLatitude] = useState(CENTRO_REGIAO.latitude);
    const [longitude, setLongitude] = useState(CENTRO_REGIAO.longitude);
    const [diasDesdeCorte, setDiasDesdeCorte] = useState(30);
    const [dataFinal, setDataFinal] = useState("");
    const [especie, setEspecie] = useState(ESPECIES[0]);

    // Estado "herdado" de um clique no mapa — não aparece no formulário, mas
    // garante que o resultado bate com o que o mapa mostra para aquele
    // trecho. Editar as coordenadas manualmente solta esse vínculo (volta a
    // ser uma consulta hipotética, igual a antes).
    const [raioMetros, setRaioMetros] = useState(500);
    const [corteOrigem, setCorteOrigem] = useState(null); // {data_corte, altura_corte_cm} | null

    // Estado da requisição
    const [carregando, setCarregando] = useState(false);
    const [erro, setErro] = useState(null);
    const [resultado, setResultado] = useState(null);
    const [alturasPorEspecie, setAlturasPorEspecie] = useState(null);
    const origemResultadoRef = useRef(null);

    const executarConsulta = async ({ lat, lon, dias, data, especieConsulta, raio }) => {
        setCarregando(true);
        setErro(null);
        try {
            const params = {
                latitude: Number(lat),
                longitude: Number(lon),
                raio_metros: raio,
                dias_desde_corte: dias,
                especie: especieConsulta,
            };
            if (data) params.data = data;

            const resposta = await axios.get(`${API_BASE}/variaveis-x`, { params });
            origemResultadoRef.current = "manual";
            setResultado({ ...resposta.data, origem: "manual" });
            setAlturasPorEspecie(null);
            return resposta.data;
        } catch (error) {
            const detalhe = error.response?.data?.detail;
            const msg = typeof detalhe === "string"
                ? detalhe
                : detalhe?.erro || error.message || "Falha ao calcular a altura.";
            setErro(msg);
            origemResultadoRef.current = null;
            setResultado(null);
            setAlturasPorEspecie(null);
            return null;
        } finally {
            setCarregando(false);
        }
    };

    // ---------- Vem do mapa: clicou numa bolinha ----------
    useEffect(() => {
        if (!celulaSelecionada) {
            if (origemResultadoRef.current === "mapa") {
                const limpeza = window.setTimeout(() => {
                    origemResultadoRef.current = null;
                    setResultado(null);
                    setCorteOrigem(null);
                    setAlturasPorEspecie(null);
                }, 0);
                return () => window.clearTimeout(limpeza);
            }
            return;
        }
        if (celulaSelecionada.preservarConsultaManual) return;

        const dias = celulaSelecionada.dias_desde_corte ?? 30;
        const data = celulaSelecionada.dataAlvo || "";
        const especieMapa = celulaSelecionada.especie || ESPECIES[0];
        const raio = celulaSelecionada.raio_metros || 500;

        const agendada = window.setTimeout(() => {
            setLatitude(celulaSelecionada.latitude);
            setLongitude(celulaSelecionada.longitude);
            setDiasDesdeCorte(dias);
            setDataFinal(data);
            setEspecie(especieMapa);
            setRaioMetros(raio);
            setCorteOrigem(celulaSelecionada.corte || null);
            origemResultadoRef.current = "mapa";
            setResultado({
                localizacao: { latitude: celulaSelecionada.latitude, longitude: celulaSelecionada.longitude, raio_metros: raio },
                previsao: { altura: celulaSelecionada.altura_cm, probabilidade: celulaSelecionada.confianca },
                especie: especieMapa,
                dias_desde_corte: dias,
                data,
                corte_recomendado: null,
                criticidade: celulaSelecionada.cor,
                clima: null,
                origem: "mapa",
            });
            setErro(null);
            setCarregando(false);
            setAlturasPorEspecie(celulaSelecionada.alturas_por_especie || null);
        }, 0);
        return () => window.clearTimeout(agendada);
    }, [celulaSelecionada]);

    // Editar lat/long manualmente solta o vínculo com o corte/espécie do
    // clique — volta a ser uma consulta hipotética a partir de 0 cm.
    const lidarComEdicaoCoordenada = (setter) => (evento) => {
        setter(evento.target.value);
        setCorteOrigem(null);
    };

    // ---------- Botão "Calcular altura": consulta manual ----------
    const calcularAltura = async () => {
        setCorteOrigem(null);
        const dados = await executarConsulta({
            lat: latitude,
            lon: longitude,
            dias: diasDesdeCorte,
            data: dataFinal,
            especieConsulta: especie,
            raio: raioMetros,
        });
        if (dados) {
            onConsultaResolvida?.({ latitude: Number(latitude), longitude: Number(longitude) });
        }
    };

    const consultaValida = latitude !== "" && longitude !== "";

    return (
        <div className="container-principal">
            <TituloCards
                icone={<FaSearchLocation color="#0c3260" size={20} fontWeight={600} />}
                texto={"Consulta Específica de Trecho"}
            />

            <div className="consulta-trecho-corpo">
                {/* ---------- Painel esquerdo: formulario ---------- */}
                <div className="painel-consulta">
                    <div className="grade-formulario">
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
                            {resultado?.origem === "mapa" && (
                                <p className="dica-consulta">
                                    <FaMapMarkerAlt className="icone-dica" />
                                    Trecho selecionado no mapa
                                </p>
                            )}
                        </div>

                        <div className="campo-toolbar">
                            <label className="rotulo-campo" htmlFor="especie-consulta">Espécie</label>
                            <select
                                id="especie-consulta"
                                className="input-consulta"
                                value={especie}
                                onChange={(e) => setEspecie(e.target.value)}
                            >
                                {ESPECIES.map((nome) => <option key={nome} value={nome}>{nome}</option>)}
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
                                {carregando ? "Gerando Projeção..." : "Gerar Projeção de Crescimento"}
                            </button>
                        </div>
                    </div>
                </div>

                {/* ---------- Painel direito: resultado em cards ---------- */}
                <div className="painel-resultado">
                    {carregando && !resultado ? (
                        <div className="consulta-carregando">
                            <span className="spinner-consulta" />
                            Calculando altura estimada...
                        </div>
                    ) : erro && !carregando ? (
                        <div className="consulta-erro">Falha na consulta: {erro}</div>
                    ) : !resultado ? (
                        <div className="consulta-vazio">
                            Clique numa bolinha do mapa ou preencha a consulta ao lado e clique em <strong>Calcular altura</strong>.
                        </div>
                    ) : (
                        <>
                            {carregando && (
                                <div className="consulta-atualizando">
                                    <span className="spinner-consulta" />
                                    Atualizando com o novo trecho...
                                </div>
                            )}
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
                                    <div className={`selo-corte ${(
                                        resultado.origem === "mapa"
                                            ? resultado.criticidade === "vermelho"
                                            : resultado.corte_recomendado
                                    ) ? "necessario" : "nao-necessario"}`}>
                                        <span className="ponto-selo" />
                                        {resultado.origem === "mapa"
                                            ? ROTULOS_STATUS[resultado.criticidade] || "Status indisponível"
                                            : resultado.corte_recomendado ? "Corte necessário" : "Corte não necessário"}
                                    </div>
                                    <p className="linha-meta">
                                        {resultado.especie} · {resultado.dias_desde_corte}d · {resultado.data}
                                    </p>
                                    {corteOrigem ? (
                                        <p className="linha-meta">
                                            <FaMapMarkerAlt className="icone-local" />
                                            Cortada em {formatarData(corteOrigem.data_corte)} a {corteOrigem.altura_corte_cm} cm
                                        </p>
                                    ) : (
                                        <p className="linha-meta">
                                            <FaMapMarkerAlt className="icone-local" />
                                            {resultado.localizacao.latitude.toFixed(2)}, {resultado.localizacao.longitude.toFixed(2)}
                                            {" "}(raio {resultado.localizacao.raio_metros} m)
                                        </p>
                                    )}
                                </div>
                            </div>

                            {resultado.clima ? <div className="grade-clima">
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
                            </div> : resultado.origem === "mapa" && (
                                <p className="dica-consulta">Clima não é incluído na varredura do mapa. Gere uma consulta hipotética para obter o resumo climático.</p>
                            )}

                            {/* Mesma tabela do popup do mapa: as 5 espécies no ponto */}
                            {alturasPorEspecie && (
                                <div className="grade-especies">
                                    <span className="titulo-especies">Todas as espécies neste ponto</span>
                                    <table className="tabela-especies">
                                        <tbody>
                                            {Object.entries(alturasPorEspecie)
                                                .sort((a, b) => b[1] - a[1])
                                                .map(([nome, altura]) => (
                                                    <tr key={nome} className={nome === resultado.especie ? "ativa" : ""}>
                                                        <td>
                                                            <span
                                                                className="swatch-clima"
                                                                style={{ backgroundColor: CORES_STATUS[altura > 25 ? "vermelho" : altura > 15 ? "amarelo" : "verde"] }}
                                                            />
                                                            {nome}
                                                        </td>
                                                        <td>{altura.toFixed(1)} cm</td>
                                                    </tr>
                                                ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

export default ConsultaTrecho;
