import "../styles/VariavelCard.css"

function VariavelCard ({ icone, titulo, valorDaVariavel, descricao }) {
    return (
        <div className="container-principal-variaveis-analisadas">
            <div className="titulo-card-variaveis-analisadas">
                <span className="icone-titulo-variaveis-analisadas">{icone}</span>
                <span>{titulo}</span>
            </div>

            <p className="variavel-analisada">{valorDaVariavel}</p>

            <p className="descricao-variaveis-analisadas">{descricao}</p>
        </div>
    )
}

export default VariavelCard;