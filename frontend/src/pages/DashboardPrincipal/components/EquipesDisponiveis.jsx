import "../styles/EquipesDisponiveis.css";
import mockData from "../mock/infoEquipesTrechosRodovia.json";

function EquipesDisponiveis({ celulasMapa }) {

    // Função para calcular matematicamente o destino mais próximo com base
    // nas células reais da última varredura do mapa (não mais num mock fixo
    // de trechos -- assim a recomendação sempre bate com o que está no mapa).
    const calcularProximoDestino = (kmEquipe, pontosProblematicos) => {
        if (pontosProblematicos.length === 0) return null;

        let maisProximo = pontosProblematicos[0];
        let menorDistancia = Math.abs(kmEquipe - maisProximo.posicaoKm);

        pontosProblematicos.forEach((ponto) => {
            const distancia = Math.abs(kmEquipe - ponto.posicaoKm);
            if (distancia < menorDistancia) {
                menorDistancia = distancia;
                maisProximo = ponto;
            }
        });

        // Simulação de cálculo de ETA (adotando média de ~1.5 minutos por km).
        const etaSimulado = Math.round(menorDistancia * 1.5);

        return {
            kmDestino: maisProximo.posicaoKm,
            distancia: Math.round(menorDistancia * 10) / 10,
            eta: etaSimulado
        };
    };

    const pontosProblematicos = (celulasMapa || []).filter((c) => c.cor !== "verde");
    const mapaAindaCarregando = !celulasMapa || celulasMapa.length === 0;

    return (
        <div className="container-equipes-disponiveis">
            <h4 className="titulo-secao-equipes">Outras Recomendações</h4>

            <div className="lista-equipes">
                {mockData.equipes.map((equipe) => {
                    const kmAtual = equipe.localizacao_km;
                    const destino = mapaAindaCarregando ? null : calcularProximoDestino(kmAtual, pontosProblematicos);

                    return (
                        <div key={equipe.id_equipe} className="card-equipe">
                            <p className="nome-equipe">
                                Equipe {equipe.nome_equipe} (Km {kmAtual})
                            </p>

                            {mapaAindaCarregando ? (
                                <p className="detalhes-equipe">Aguardando a varredura do mapa...</p>
                            ) : destino ? (
                                <p className="detalhes-equipe">
                                    Distância para ponto de atenção mais próximo (Km {destino.kmDestino}): {destino.distancia}km (ETA {destino.eta} min).
                                </p>
                            ) : (
                                <p className="detalhes-equipe">Nenhum ponto crítico identificado na via.</p>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

export default EquipesDisponiveis;
