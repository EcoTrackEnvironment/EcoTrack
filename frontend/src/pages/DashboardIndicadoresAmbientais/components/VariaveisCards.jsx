import "../styles/VariavelCard.css"

function VariavelCard ({ icone, titulo, valorDaVariavel, descricao }) {
    return (
        <div className="container-principal-card">
            <div className="titulo-card">
                <span className="icone-titulo">{icone}</span>
                <span>{titulo}</span>
            </div>

            <p className="variavel">{valorDaVariavel}</p>

            <p className="descricao">{descricao}</p>
        </div>
    )
}

export default VariavelCard;