import { useState, useEffect, useRef, useMemo } from "react";
import axios from "axios";
import TituloCards from "./TituloCards"
import "../styles/EsqueletoCards.css"
import "../styles/GraficoLinha.css"
import { FaChartLine } from "react-icons/fa6";
import { API_BASE_URL, dataLocalISO } from "../../../api/client";

// Uma cor por espécie, em ordem fixa — a cor segue a espécie, nunca a posição
// na lista. Azul, roxo, laranja, rosa e ciano: nenhuma delas colide com o
// verde/amarelo/vermelho que o mapa usa para status, e o conjunto passa nos
// checks de daltonismo para todos os pares (pior ΔE 15.1, alvo 8).
const CORES_ESPECIE = {
    "Brachiaria (Urochloa)": "#4087fd",
    "Cynodon (grama-seda)": "#6c02cf",
    "Megathyrsus (capim-coloniao)": "#ef5d0d",
    "Pennisetum (capim-elefante)": "#a7016d",
    "Paspalum (grama-batatais)": "#1ab9cc",
};
const COR_RESERVA = "#4087fd";

// Período inicial: do corte de hoje até 90 dias à frente. Em 30 dias de
// inverno as cinco linhas ficam quase coladas no eixo e o gráfico não diz nada.
const DIAS_PADRAO = 90;
const isoDeHoje = dataLocalISO;

const VB = { largura: 760, altura: 260, esq: 58, dir: 14, topo: 14, base: 28 };
const X0 = VB.esq;
const X1 = VB.largura - VB.dir;
const Y0 = VB.altura - VB.base;
const Y1 = VB.topo;

// Teto do eixo Y arredondado para um número redondo acima do maior valor.
function tetoEixo(valorMax) {
    if (valorMax <= 0) return 10;
    const passo = valorMax > 200 ? 50 : valorMax > 100 ? 25 : valorMax > 40 ? 10 : 5;
    return Math.ceil(valorMax / passo) * passo;
}

function formatarData(iso) {
    const [, mes, dia] = iso.split("-");
    return `${dia}/${mes}`;
}

function GraficoLinha({ celula, onLimparCelula }) {
    const [dados, setDados] = useState(null);
    const [erro, setErro] = useState(null);
    const [foco, setFoco] = useState(null);   // índice do dia sob o cursor
    // Vazio = "usar o corte REGISTRADO no banco para este ponto" (data e altura).
    // O operador ainda pode digitar outra data para simular um corte hipotético.
    const [inicio, setInicio] = useState("");
    const [fim, setFim] = useState(isoDeHoje(DIAS_PADRAO));
    // Chave da consulta já resolvida — comparar com a chave atual dá o estado de
    // carregamento sem precisar setar estado dentro do efeito.
    const [chaveResolvida, setChaveResolvida] = useState(null);
    const svgRef = useRef(null);

    const periodoInvalido = !fim || (!!inicio && fim <= inicio);
    const chave = `${inicio}|${fim}|${celula ? `${celula.latitude},${celula.longitude}` : "regiao"}`;
    const carregando = !periodoInvalido && chave !== chaveResolvida;
    // Enquanto o operador não escolhe uma data, o campo mostra a do corte que o
    // backend resolveu — sem virar estado, o que evitaria um refetch em looping.
    const valorInicio = inicio || dados?.inicio || "";

    // Refaz a série quando muda o período OU o trecho selecionado no mapa.
    useEffect(() => {
        if (periodoInvalido) return;
        const params = new URLSearchParams({ fim });
        if (inicio) params.set("inicio", inicio);
        if (celula) {
            params.set("latitude", celula.latitude);
            params.set("longitude", celula.longitude);
        }
        let cancelado = false;
        axios
            .get(`${API_BASE_URL}/crescimento/serie?${params}`)
            .then((r) => {
                if (cancelado) return;
                setDados(r.data);
                setErro(null);
                setFoco(null);
            })
            .catch((e) => {
                if (cancelado) return;
                console.error("ERRO na série de crescimento: ", e);
                setErro(e.response?.data?.detail || e.message);
            })
            .finally(() => { if (!cancelado) setChaveResolvida(chave); });
        return () => { cancelado = true; };
    }, [inicio, fim, celula, periodoInvalido, chave]);

    const grafico = useMemo(() => {
        if (!dados) return null;
        const nomes = dados.especies.filter((n) => dados.series[n]?.length);
        const n = dados.datas.length;
        const limiar = dados.altura_corte_recomendado_cm;
        const maxSerie = Math.max(...nomes.flatMap((nome) => dados.series[nome]));
        const teto = tetoEixo(Math.max(maxSerie, limiar));

        const px = (i) => X0 + (i * (X1 - X0)) / Math.max(n - 1, 1);
        const py = (v) => Y0 - (v / teto) * (Y0 - Y1);

        const linhas = nomes.map((nome) => ({
            nome,
            cor: CORES_ESPECIE[nome] || COR_RESERVA,
            d: dados.series[nome].map((v, i) => `${i ? "L" : "M"}${px(i).toFixed(1)} ${py(v).toFixed(1)}`).join(" "),
        }));

        // 5 marcas no eixo Y e ~6 datas no X, sem poluir.
        const marcasY = Array.from({ length: 5 }, (_, k) => (teto * k) / 4);
        const passoX = Math.max(1, Math.round((n - 1) / 5));
        const marcasX = [];
        for (let i = 0; i < n; i += passoX) marcasX.push(i);
        if (marcasX[marcasX.length - 1] !== n - 1) marcasX.push(n - 1);

        return { nomes, n, teto, limiar, px, py, linhas, marcasY, marcasX };
    }, [dados]);

    // O crosshair encontra o X: o leitor mira numa data, não numa linha de 2px.
    const moverCursor = (evt) => {
        if (!grafico || !svgRef.current) return;
        const caixa = svgRef.current.getBoundingClientRect();
        const xVb = ((evt.clientX - caixa.left) / caixa.width) * VB.largura;
        const razao = (xVb - X0) / (X1 - X0);
        const i = Math.round(razao * (grafico.n - 1));
        setFoco(i >= 0 && i < grafico.n ? i : null);
    };

    return (
        <div className="container-principal">
            <TituloCards icone={<FaChartLine color="#0c3260" size={20} fontWeight={600} />} texto={"Tendência de Crescimento Estimado"} />

            <div className="grafico-card">
                <div className="grafico-controles">
                    <label htmlFor="grafico-inicio">Corte em:</label>
                    <input id="grafico-inicio" type="date" className="input-date"
                        value={valorInicio} onChange={(e) => setInicio(e.target.value)} />
                    <label htmlFor="grafico-fim">até:</label>
                    <input id="grafico-fim" type="date" className="input-date"
                        value={fim} onChange={(e) => setFim(e.target.value)} />

                    <span className="grow"></span>

                    {celula ? (
                        <span className="chip-trecho">
                            Trecho {celula.latitude.toFixed(4)}, {celula.longitude.toFixed(4)}
                            <button className="btn-limpar" onClick={() => onLimparCelula?.()} title="Voltar para o centro da região">✕</button>
                        </span>
                    ) : (
                        <span className="chip-trecho chip-trecho-vazio">
                            Centro da região · clique numa célula do mapa
                        </span>
                    )}
                </div>

                {periodoInvalido && (
                    <div className="grafico-erro">A data final precisa ser posterior à data do corte.</div>
                )}
                {erro && !periodoInvalido && <div className="grafico-erro">Falha ao carregar a série: {String(erro)}</div>}
                {!dados && !erro && !periodoInvalido && (
                    <div className="grafico-carregando">Calculando o crescimento dia a dia...</div>
                )}

                {grafico && !periodoInvalido && !erro && (
                    <>
                        <div className="grafico-legenda">
                            {grafico.nomes.map((nome) => (
                                <span className="legenda-item" key={nome}>
                                    <span className="legenda-traco" style={{ backgroundColor: CORES_ESPECIE[nome] || COR_RESERVA }}></span>
                                    {nome}
                                </span>
                            ))}
                        </div>

                        {/* Enquanto recarrega, o gráfico segura o desenho anterior esmaecido:
                            sem skeleton, sem pulo de layout. */}
                        <div className={`grafico-area${carregando ? " recarregando" : ""}`}>
                            <svg
                                ref={svgRef}
                                viewBox={`0 0 ${VB.largura} ${VB.altura}`}
                                className="grafico-svg"
                                role="img"
                                aria-label="Altura estimada da grama por espécie ao longo do tempo"
                                onMouseMove={moverCursor}
                                onMouseLeave={() => setFoco(null)}
                            >
                                {grafico.marcasY.map((v, k) => (
                                    <g key={v}>
                                        <line x1={X0} x2={X1} y1={grafico.py(v)} y2={grafico.py(v)} className="grade" />
                                        {/* a unidade acompanha só a marca do topo, para não repetir "cm" em toda linha */}
                                        <text x={X0 - 8} y={grafico.py(v) + 4} className="rotulo-eixo" textAnchor="end">
                                            {k === grafico.marcasY.length - 1 ? `${v} cm` : v}
                                        </text>
                                    </g>
                                ))}

                                {grafico.marcasX.map((i) => (
                                    <text key={i} x={grafico.px(i)} y={Y0 + 17} className="rotulo-eixo" textAnchor="middle">
                                        {formatarData(dados.datas[i])}
                                    </text>
                                ))}

                                {/* altura a partir da qual o corte é recomendado */}
                                <line x1={X0} x2={X1} y1={grafico.py(grafico.limiar)} y2={grafico.py(grafico.limiar)} className="linha-limiar" />
                                <text x={X1} y={grafico.py(grafico.limiar) - 5} className="rotulo-limiar" textAnchor="end">
                                    corte recomendado ({grafico.limiar} cm)
                                </text>

                                {foco !== null && (
                                    <line x1={grafico.px(foco)} x2={grafico.px(foco)} y1={Y1} y2={Y0} className="crosshair" />
                                )}

                                {grafico.linhas.map((l) => (
                                    <path key={l.nome} d={l.d} fill="none" stroke={l.cor} strokeWidth="2"
                                        strokeLinejoin="round" strokeLinecap="round" />
                                ))}

                                {foco !== null && grafico.linhas.map((l) => (
                                    <circle key={l.nome} cx={grafico.px(foco)} cy={grafico.py(dados.series[l.nome][foco])}
                                        r="4" fill={l.cor} stroke="#ffffff" strokeWidth="2" />
                                ))}
                            </svg>

                            {foco !== null && (
                                <div
                                    className="grafico-tooltip"
                                    style={{
                                        left: `${(grafico.px(foco) / VB.largura) * 100}%`,
                                        transform: grafico.px(foco) > VB.largura / 2 ? "translateX(-104%)" : "translateX(4%)",
                                    }}
                                >
                                    <div className="tooltip-data">{dados.datas[foco].split("-").reverse().join("/")}</div>
                                    {grafico.nomes
                                        .map((nome) => ({ nome, valor: dados.series[nome][foco] }))
                                        .sort((a, b) => b.valor - a.valor)
                                        .map(({ nome, valor }) => (
                                            <div className="tooltip-linha" key={nome}>
                                                <span className="tooltip-traco" style={{ backgroundColor: CORES_ESPECIE[nome] || COR_RESERVA }}></span>
                                                <strong>{valor.toFixed(1)} cm</strong>
                                                <span className="tooltip-nome">{nome}</span>
                                            </div>
                                        ))}
                                </div>
                            )}
                        </div>

                        <div className="grafico-rodape">
                            {dados.dias} dias desde o corte · parte de {dados.altura_inicial_cm} cm
                            {!inicio && dados.corte && (
                                dados.corte.escopo === "global"
                                    ? " (roçada geral registrada)"
                                    : " (corte registrado neste trecho)"
                            )}
                            {" · clima: "}{dados.fonte_clima}
                        </div>
                    </>
                )}
            </div>
        </div>
    )
}

export default GraficoLinha
