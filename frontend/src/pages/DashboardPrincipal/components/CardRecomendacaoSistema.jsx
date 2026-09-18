import "../styles/CardRecomendacaoSistema.css"

function RecomendacaoSistema({ icone, titulo, qtd_trechos_criticos, descricao_recomendacao, onClickAtivar }) {
    
    const textoSemPrefixo = descricao_recomendacao.replace("Recomendação:", "").trim();
    const lidarComClique = () => {
        onClickAtivar?.();
    }

    return (
        <div className="container-card-recomendacao">
            
            <div className="container-titulo-recomendacao">
                <h6 className="titulo-recomendacao">
                    <span className="icone-recomendacao">{icone}</span> 
                    {titulo}
                </h6>
            </div>

            <div className="container-descricao-recomendacao">
                <p className="texto-alerta">
                    {qtd_trechos_criticos}
                </p>
                <p className="texto-recomendacao">
                    <strong>Recomendação:</strong> {textoSemPrefixo}
                </p>
                
                <button className="botao-ativar-alocacao" onClick={lidarComClique}>
                    Ver trecho recomendado
                </button>
            </div>

        </div>
    )
}

export default RecomendacaoSistema;
