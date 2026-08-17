import { useState } from "react"
import "./index.css"
import GraficoLinha from "./components/GraficoLinha"
import ConsultaTrecho from "./components/ConsultaTrecho"
import VariaveisAnalisadas from "./components/VariaveisAnalisadas"
import DecisoesEAlocacao from "./components/DecisoesEAlocacao"
import Mapa from "./components/Mapa"
import Exportacao from "./components/Exportacao"

function HomePrincipal() {
  // Célula do mapa selecionada pelo operador. Fica aqui, e não dentro do mapa,
  // porque o gráfico de tendência precisa saber qual trecho está em foco.
  const [celulaSelecionada, setCelulaSelecionada] = useState(null)

  return (
    <div className="container">
        <div className="div-main">
            <div className="div-mapa-alocacao">
                <div className="mapa">
                    <Mapa
                        celulaSelecionada={celulaSelecionada}
                        onSelecionarCelula={setCelulaSelecionada}
                    />
                </div>

                <div className="alocacao">
                    <DecisoesEAlocacao/>
                </div>
            </div>


            <div className="div-grafico-infos">
                <div className="grafico">
                    <GraficoLinha
                        celula={celulaSelecionada}
                        onLimparCelula={() => setCelulaSelecionada(null)}
                    />
                </div>

                <div className="infos">
                    <VariaveisAnalisadas/>
                </div>
            </div>


            <div className="div-consulta">
                <ConsultaTrecho/>
            </div>


            <div className="div-exportacao">
                <Exportacao/>
            </div>
        </div>
    </div>
  )
}

export default HomePrincipal
