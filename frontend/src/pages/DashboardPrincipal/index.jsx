import { useState, useCallback } from "react"
import "./index.css"
// import GraficoLinha from "./components/GraficoLinha"
import ConsultaTrecho from "./components/ConsultaTrecho"
// import VariaveisAnalisadas from "./components/VariaveisAnalisadas"
import DecisoesEAlocacao from "./components/DecisoesEAlocacao"
import Mapa from "./components/Mapa"
import Exportacao from "./components/Exportacao"

// Distância aproximada em km entre dois pontos, na latitude da RMSP — mesma
// aproximação usada dentro do Mapa (SelecaoPorProximidade) para "clicar perto
// já seleciona a célula". Aqui serve pro caminho inverso: uma busca feita
// pelo card de Consulta acha a bolinha real mais próxima para destacar.
function distanciaKm(lat1, lon1, lat2, lon2) {
  const dLat = (lat2 - lat1) * 111.0
  const dLon = (lon2 - lon1) * 111.32 * Math.cos((lat1 * Math.PI) / 180)
  return Math.hypot(dLat, dLon)
}

function HomePrincipal() {
  // Célula do mapa selecionada pelo operador. Fica aqui, e não dentro do mapa,
  // porque o card de Consulta Específica de Trecho precisa saber qual trecho
  // está em foco (e vice-versa: uma busca pelo card também seleciona aqui).
  const [celulaSelecionada, setCelulaSelecionada] = useState(null)
  // Células da última varredura do mapa — só para achar "a bolinha mais
  // próxima" quando a seleção vem do card, não do mapa.
  const [celulasMapa, setCelulasMapa] = useState([])

  // Consulta manual resolvida no card -> acha a célula real mais próxima
  // (mesmo raio de 3km do clique no mapa) e a seleciona, para o mapa
  // destacar o mesmo trecho. Sem célula por perto, não seleciona nada.
  const lidarComConsultaResolvida = useCallback(({ latitude, longitude }) => {
    if (!celulasMapa || celulasMapa.length === 0) return
    let maisProxima = null
    let menorDistancia = Infinity
    for (const c of celulasMapa) {
      const d = distanciaKm(latitude, longitude, c.latitude, c.longitude)
      if (d < menorDistancia) { menorDistancia = d; maisProxima = c }
    }
    if (maisProxima && menorDistancia <= 3) {
      setCelulaSelecionada(maisProxima)
    }
  }, [celulasMapa])

  return (
    <div className="container">
        <div className="div-main">
            <div className="div-mapa-alocacao">
                <div className="mapa">
                    <Mapa
                        celulaSelecionada={celulaSelecionada}
                        onSelecionarCelula={setCelulaSelecionada}
                        onCelulasCarregadas={setCelulasMapa}
                    />
                </div>

                <div className="alocacao">
                    <DecisoesEAlocacao/>
                </div>
            </div>


            {/* <div className="div-grafico-infos">
                <div className="grafico">
                    <GraficoLinha
                        celula={celulaSelecionada}
                        onLimparCelula={() => setCelulaSelecionada(null)}
                    />
                </div>

                <div className="infos">
                    <VariaveisAnalisadas/>
                </div>
            </div> */}


            <div className="div-consulta">
                <ConsultaTrecho
                    celulaSelecionada={celulaSelecionada}
                    onConsultaResolvida={lidarComConsultaResolvida}
                />
            </div>


            <div className="div-exportacao">
                <Exportacao/>
            </div>
        </div>
    </div>
  )
}

export default HomePrincipal