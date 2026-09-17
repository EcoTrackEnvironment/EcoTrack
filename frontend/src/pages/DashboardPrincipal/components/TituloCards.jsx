import "../styles/TituloCards.css"

function TituloCards({icone, texto}) {
  return (
    <div className="container-titulo">
        <h5 className="titulo-card">
            <span className="icone-titulo">{icone}</span> 
            {texto}
        </h5>
    </div>
  )
}

export default TituloCards