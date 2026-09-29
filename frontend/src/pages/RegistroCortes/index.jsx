// Tela "Registro de Cortes".
//
// É por aqui que o estado inicial do modelo de crescimento deixa de ser uma
// premissa e vira dado: o operador informa QUANDO a roçada aconteceu e a QUE
// ALTURA a grama ficou, para a rodovia inteira ou para um trecho específico
// escolhido no mapa. O backend grava no banco (tabela `cortes`) e o mapa
// operacional passa a simular a partir desse ponto de partida.
import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { FaCut, FaMapMarkerAlt, FaTrash, FaRoad, FaInfoCircle } from "react-icons/fa";

import MapaCortes from "./components/MapaCortes";
import { API_BASE_URL, dataLocalISO } from "../../api/client";
import "./RegistroCortes.css";

const API_BASE = API_BASE_URL;

const hojeISO = () => dataLocalISO();

const formatarData = (iso) => {
    if (!iso) return "—";
    const [ano, mes, dia] = iso.split("-");
    return `${dia}/${mes}/${ano}`;
};

const diasDesde = (iso) => {
    if (!iso) return null;
    const corte = new Date(`${iso}T00:00:00`);
    const hoje = new Date(`${hojeISO()}T00:00:00`);
    return Math.round((hoje - corte) / 86400000);
};

function RegistroCortes() {
    // ---- formulário -------------------------------------------------------
    const [escopo, setEscopo] = useState("ponto");        // "ponto" | "global"
    const [latitude, setLatitude] = useState("");
    const [longitude, setLongitude] = useState("");
    const [raio, setRaio] = useState(300);
    const [dataCorte, setDataCorte] = useState(hojeISO());
    const [alturaCorte, setAlturaCorte] = useState(2);
    const [observacao, setObservacao] = useState("");

    // ---- dados / estado da tela ------------------------------------------
    const [cortes, setCortes] = useState([]);
    // Guardado junto com a chave que o originou: assim o card só aparece quando
    // corresponde ao ponto atual, sem precisar limpá-lo dentro do efeito.
    const [vigenteBuscado, setVigenteBuscado] = useState(null);
    const [salvando, setSalvando] = useState(false);
    const [erro, setErro] = useState(null);
    const [aviso, setAviso] = useState(null);
    // Muda a cada gravação: força o mapa a refazer a varredura com o corte novo.
    const [versaoMapa, setVersaoMapa] = useState(0);

    const carregarCortes = useCallback(() => {
        axios
            .get(`${API_BASE}/cortes`)
            .then((resposta) => setCortes(resposta.data || []))
            .catch((error) => setErro(error.message));
    }, []);

    useEffect(() => { carregarCortes(); }, [carregarCortes]);

    // Qual corte o sistema está usando HOJE no ponto escolhido — é o que o
    // registro novo vai substituir.
    const chaveVigente =
        escopo === "ponto" && latitude !== "" && longitude !== ""
            ? `${latitude},${longitude}|${versaoMapa}`
            : null;

    useEffect(() => {
        if (!chaveVigente) return;
        const [coordenadas] = chaveVigente.split("|");
        const [lat, lon] = coordenadas.split(",");
        let cancelado = false;
        axios
            .get(`${API_BASE}/cortes/vigente`, { params: { latitude: lat, longitude: lon } })
            .then((resposta) => {
                if (!cancelado) setVigenteBuscado({ chave: chaveVigente, corte: resposta.data });
            })
            .catch(() => {
                if (!cancelado) setVigenteBuscado({ chave: chaveVigente, corte: null });
            });
        return () => { cancelado = true; };
    }, [chaveVigente]);

    const corteVigente =
        chaveVigente && vigenteBuscado?.chave === chaveVigente ? vigenteBuscado.corte : null;

    const selecionarPonto = useCallback((celula) => {
        setEscopo("ponto");
        setLatitude(celula.latitude);
        setLongitude(celula.longitude);
        setAviso(null);
    }, []);

    const pontoSelecionado =
        escopo === "ponto" && latitude !== "" && longitude !== ""
            ? { latitude: Number(latitude), longitude: Number(longitude) }
            : null;

    const formularioValido =
        dataCorte &&
        dataCorte <= hojeISO() &&
        alturaCorte !== "" &&
        Number(alturaCorte) >= 0 &&
        Number(alturaCorte) <= 50 &&
        (escopo === "global" || (latitude !== "" && longitude !== ""));

    const registrar = async (evento) => {
        evento.preventDefault();
        setSalvando(true);
        setErro(null);
        setAviso(null);
        try {
            const corpo = {
                data_corte: dataCorte,
                altura_corte_cm: Number(alturaCorte),
                observacao: observacao.trim() || null,
            };
            if (escopo === "ponto") {
                corpo.latitude = Number(latitude);
                corpo.longitude = Number(longitude);
                corpo.raio_influencia_m = Number(raio);
            }
            const resposta = await axios.post(`${API_BASE}/cortes`, corpo);
            setAviso(
                resposta.data.escopo === "global"
                    ? `Corte geral registrado: toda a rodovia parte de ${resposta.data.altura_corte_cm} cm em ${formatarData(resposta.data.data_corte)}.`
                    : `Corte registrado no trecho (${resposta.data.latitude}, ${resposta.data.longitude}), num raio de ${resposta.data.raio_influencia_m} m.`
            );
            setObservacao("");
            carregarCortes();
            setVersaoMapa((v) => v + 1);
        } catch (error) {
            const detalhe = error.response?.data?.detail;
            setErro(
                typeof detalhe === "string"
                    ? detalhe
                    : detalhe?.[0]?.msg || error.message || "Falha ao registrar o corte."
            );
        } finally {
            setSalvando(false);
        }
    };

    const remover = async (corte) => {
        setErro(null);
        setAviso(null);
        try {
            await axios.delete(`${API_BASE}/cortes/${corte.id}`);
            setAviso(`Registro de ${formatarData(corte.data_corte)} removido — o corte anterior volta a valer nesse trecho.`);
            carregarCortes();
            setVersaoMapa((v) => v + 1);
        } catch (error) {
            const detalhe = error.response?.data?.detail;
            setErro(typeof detalhe === "string" ? detalhe : error.message);
        }
    };

    return (
        <div className="cortes-container">
            <div className="cortes-header">
                <h2><FaCut /> Registro de Cortes</h2>
                <p>
                    Informe quando cada trecho foi roçado e a que altura a grama ficou. É
                    daqui que o modelo de crescimento tira o ponto de partida da projeção de crescimento.
                </p>
            </div>

            <div className="cortes-conteudo">
                {/* ------------------------- Mapa ------------------------- */}
                <section className="cortes-card cortes-card-mapa">
                    <h3><FaMapMarkerAlt /> Escolha o trecho</h3>
                    <p className="cortes-card-descricao">
                        Clique numa bolinha para carregar a coordenada no
                        formulário. As cores são o status atual da via, os anéis tracejados
                        são trechos que já possuem corte registrado.
                    </p>
                    <MapaCortes
                        pontoSelecionado={pontoSelecionado}
                        onSelecionarPonto={selecionarPonto}
                        cortes={cortes}
                        versao={versaoMapa}
                    />
                    <div className="cortes-legenda">
                        <span className="item"><span className="sw verde"></span>1–15 cm</span>
                        <span className="item"><span className="sw amarelo"></span>16–25 cm</span>
                        <span className="item"><span className="sw vermelho"></span>&gt; 25 cm</span>
                        <span className="item"><span className="sw anel"></span>trecho com corte próprio</span>
                    </div>
                </section>

                {/* ---------------------- Formulário ---------------------- */}
                <section className="cortes-card">
                    <h3><FaCut /> Dados do corte</h3>

                    <form onSubmit={registrar} className="cortes-form">
                        <div className="cortes-escopo">
                            <button
                                type="button"
                                className={`escopo-btn ${escopo === "ponto" ? "ativo" : ""}`}
                                onClick={() => setEscopo("ponto")}
                            >
                                <FaMapMarkerAlt />
                                <div>
                                    <strong>Trecho específico</strong>
                                    <span>Vale só no entorno da coordenada</span>
                                </div>
                            </button>
                            <button
                                type="button"
                                className={`escopo-btn ${escopo === "global" ? "ativo" : ""}`}
                                onClick={() => setEscopo("global")}
                            >
                                <FaRoad />
                                <div>
                                    <strong>Rodovia inteira</strong>
                                    <span>Roçada geral, vale em todo o anel</span>
                                </div>
                            </button>
                        </div>

                        {escopo === "ponto" && (
                            <>
                                <div className="cortes-linha">
                                    <label>
                                        Latitude
                                        <input
                                            type="number"
                                            step="0.00001"
                                            value={latitude}
                                            onChange={(e) => setLatitude(e.target.value)}
                                            placeholder="clique no mapa ou digite"
                                        />
                                    </label>
                                    <label>
                                        Longitude
                                        <input
                                            type="number"
                                            step="0.00001"
                                            value={longitude}
                                            onChange={(e) => setLongitude(e.target.value)}
                                            placeholder="clique no mapa ou digite"
                                        />
                                    </label>
                                </div>

                                <label>
                                    Alcance do corte (m)
                                    <input
                                        type="number"
                                        min="50"
                                        max="20000"
                                        step="50"
                                        value={raio}
                                        onChange={(e) => setRaio(e.target.value)}
                                    />
                                    <small>
                                        Todas as células dentro deste raio passam a usar este corte.
                                        300 m cobre a bolinha clicada e as vizinhas imediatas.
                                    </small>
                                </label>
                            </>
                        )}

                        <div className="cortes-linha">
                            <label>
                                Data do corte
                                <input
                                    type="date"
                                    max={hojeISO()}
                                    value={dataCorte}
                                    onChange={(e) => setDataCorte(e.target.value)}
                                />
                            </label>
                            <label>
                                Altura do corte (cm)
                                <input
                                    type="number"
                                    min="0"
                                    max="50"
                                    step="0.5"
                                    value={alturaCorte}
                                    onChange={(e) => setAlturaCorte(e.target.value)}
                                />
                            </label>
                        </div>

                        <label>
                            Observação (opcional)
                            <input
                                type="text"
                                maxLength={500}
                                value={observacao}
                                onChange={(e) => setObservacao(e.target.value)}
                                placeholder="ex.: equipe 3, roçadeira mecânica"
                            />
                        </label>

                        {corteVigente && (
                            <div className="cortes-vigente">
                                <FaInfoCircle />
                                <span>
                                    Hoje este ponto usa o corte de{" "}
                                    <strong>{formatarData(corteVigente.data_corte)}</strong> a{" "}
                                    <strong>{corteVigente.altura_corte_cm} cm</strong>{" "}
                                    ({corteVigente.escopo === "global" ? "roçada geral" : "trecho específico"}
                                    {diasDesde(corteVigente.data_corte) !== null && `, há ${diasDesde(corteVigente.data_corte)} dias`}).
                                </span>
                            </div>
                        )}

                        {erro && <div className="cortes-alerta erro">{erro}</div>}
                        {aviso && <div className="cortes-alerta sucesso">{aviso}</div>}

                        <button type="submit" className="cortes-submit" disabled={!formularioValido || salvando}>
                            {salvando ? "Gravando..." : "Registrar corte"}
                        </button>
                    </form>
                </section>
            </div>

            {/* ------------------------- Histórico ------------------------- */}
            <section className="cortes-card">
                <h3>Cortes registrados</h3>
                <p className="cortes-card-descricao">
                    Nada é sobrescrito, cada linha é um registro. Em cada ponto vale o corte
                    mais recente. Apagar
                    um registro faz o anterior voltar a valer.
                </p>

                <div className="cortes-tabela-wrapper">
                    <table className="cortes-tabela">
                        <thead>
                            <tr>
                                <th>Data</th>
                                <th>Abrangência</th>
                                <th className="n">Altura</th>
                                <th className="n">Alcance</th>
                                <th>Observação</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {cortes.length === 0 && (
                                <tr><td colSpan={6} className="vazio">Nenhum corte registrado.</td></tr>
                            )}
                            {cortes.map((corte) => (
                                <tr key={corte.id}>
                                    <td>
                                        {formatarData(corte.data_corte)}
                                        <small> · há {diasDesde(corte.data_corte)} d</small>
                                    </td>
                                    <td>
                                        {corte.escopo === "global" ? (
                                            <span className="tag tag-global">Rodovia inteira</span>
                                        ) : (
                                            <span className="tag">
                                                {corte.latitude.toFixed(4)}, {corte.longitude.toFixed(4)}
                                            </span>
                                        )}
                                    </td>
                                    <td className="n">{corte.altura_corte_cm} cm</td>
                                    <td className="n">
                                        {corte.raio_influencia_m ? `${corte.raio_influencia_m} m` : "—"}
                                    </td>
                                    <td className="obs">{corte.observacao || "—"}</td>
                                    <td>
                                        <button
                                            type="button"
                                            className="cortes-remover"
                                            title="Remover registro"
                                            onClick={() => remover(corte)}
                                        >
                                            <FaTrash />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}

export default RegistroCortes;
