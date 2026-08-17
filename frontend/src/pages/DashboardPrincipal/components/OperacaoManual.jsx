import { useState } from "react";
import "../styles/OperacaoManual.css";
import mockData from "../mock/infoEquipesTrechosRodovia.json";
import { FaInfoCircle, FaMapMarkerAlt } from "react-icons/fa";
import { ToastContainer, toast } from 'react-toastify';

function OperacaoManual(onClickAlocarManualmente) {
    const [alvoSelecionado, setAlvoSelecionado] = useState("");
    
    // 1. O estado agora guarda apenas um ID, não um array.
    const [equipeSelecionada, setEquipeSelecionada] = useState(null);

    // Filtra matematicamente apenas os trechos que requerem atenção (exclui os "OK")
    const trechosCriticos = mockData.trechos_rodovia.filter(t => t.status !== "OK");

    // 2. A função apenas sobrescreve o valor anterior com o novo ID selecionado.
    const handleSelecaoEquipe = (idEquipe) => {
        setEquipeSelecionada(idEquipe);
    };

    const notify = () => toast.success("Alocação realizada com sucesso!");

    const lidarComClique = () => {
        onClickAlocarManualmente;
        notify();
    }

    return (
        <div className="container-operacao-manual">
            
            {/* --- PASSO 1: O PROBLEMA --- */}
            <div className="passo-container">
                <div className="titulo-passo">Passo 1: Selecione o trecho alvo</div>
                <div className="conteudo-passo">
                    <select 
                        className="select-alvo"
                        value={alvoSelecionado}
                        onChange={(e) => setAlvoSelecionado(e.target.value)}
                    >
                        <option value="" disabled>[ Selecione o KM Crítico ]</option>
                        {trechosCriticos.map(trecho => (
                            <option key={trecho.km} value={trecho.km}>
                                RodoAnel KM {trecho.km} ({trecho.status})
                            </option>
                        ))}
                    </select>
                    <p className="info-texto">
                        <FaInfoCircle className="icone-info"/>
                        Exibe apenas os KMs em estado de Atenção ou Crítico
                    </p>
                </div>
            </div>

            {/* --- PASSO 2: A SOLUÇÃO --- */}
            <div className="passo-container">
                <div className="titulo-passo">Passo 2: Selecione a equipe</div>
                <div className="conteudo-passo lista-equipes-manual">
                    {mockData.equipes.map(equipe => {
                        // Trata a localização e calcula a distância absoluta dinamicamente se houver um alvo
                        const kmEquipe = equipe.localizacao_km || equipe.localizaca_km;
                        const distancia = alvoSelecionado ? Math.abs(kmEquipe - Number(alvoSelecionado)) : null;
                        
                        return (
                            <label key={equipe.id_equipe} className="card-equipe-checkbox">
                                {/* 3. Input alterado para type="radio" */}
                                <input 
                                    type="radio" 
                                    name="selecao_equipe"
                                    checked={equipeSelecionada === equipe.id_equipe}
                                    onChange={() => handleSelecaoEquipe(equipe.id_equipe)}
                                />
                                <div className="info-equipe-manual">
                                    <span className="nome-equipe-manual">Equipe {equipe.nome_equipe} (KM {kmEquipe})</span>
                                    <span className="status-equipe-manual">
                                        Status: Disponível 
                                        {alvoSelecionado && ` (Distância ao Alvo: ${distancia}km)`}
                                    </span>
                                </div>
                            </label>
                        );
                    })}
                </div>
            </div>

            {/* --- PASSO 3: AÇÃO --- */}
            <div className="passo-container passo-3-container">
                <div className="conteudo-passo">
                    <button 
                        className="botao-despachar"
                        // 4. O botão avalia se há um valor válido na variável equipeSelecionada
                        disabled={!alvoSelecionado || !equipeSelecionada}
                        onClick={lidarComClique}
                    >
                        <FaMapMarkerAlt className="icone-mapa" />
                        Alocar equipe
                    </button>
                    <ToastContainer/>
                </div>
            </div>

        </div>
    );
}

export default OperacaoManual;