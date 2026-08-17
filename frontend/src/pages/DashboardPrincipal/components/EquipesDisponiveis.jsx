import "../styles/EquipesDisponiveis.css";
import mockData from "../mock/infoEquipesTrechosRodovia.json";

function EquipesDisponiveis() {
    
    // Função para calcular matematicamente o destino mais próximo com base nos dados do mock
    const calcularProximoDestino = (kmEquipe) => {
        const trechosProblematicos = mockData.trechos_rodovia.filter(trecho => trecho.status !== "OK");
        
        if (trechosProblematicos.length === 0) return null;

        let maisProximo = trechosProblematicos[0];
        let menorDistancia = Math.abs(kmEquipe - maisProximo.km);

        trechosProblematicos.forEach(trecho => {
            const distancia = Math.abs(kmEquipe - trecho.km);
            if (distancia < menorDistancia) {
                menorDistancia = distancia;
                maisProximo = trecho;
            }
        });

        // Simulação de cálculo de ETA (adotando média de ~1.2 minutos para percorrer 1 km)
        const etaSimulado = Math.round(menorDistancia * 1.5); 

        return {
            kmDestino: maisProximo.km,
            distancia: menorDistancia,
            eta: etaSimulado
        };
    };

    return (
        <div className="container-equipes-disponiveis">
            <h4 className="titulo-secao-equipes">Outras Recomendações</h4>
            
            <div className="lista-equipes">
                {mockData.equipes.map((equipe) => {
                    // Tratamento provisório de tolerância a falha (fallback) devido ao erro de digitação no JSON
                    const kmAtual = equipe.localizacao_km;
                    const destino = calcularProximoDestino(kmAtual);

                    return (
                        <div key={equipe.id_equipe} className="card-equipe">
                            <p className="nome-equipe">
                                Equipe {equipe.nome_equipe} (Km {kmAtual})
                            </p>
                            
                            {destino ? (
                                <p className="detalhes-equipe">
                                    Distância para ponto crítico mais próximo (Km {destino.kmDestino}): {destino.distancia}km (ETA {destino.eta} min).
                                </p>
                            ) : (
                                <p className="detalhes-equipe">Nenhum ponto de atenção identificado na via.</p>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

export default EquipesDisponiveis;