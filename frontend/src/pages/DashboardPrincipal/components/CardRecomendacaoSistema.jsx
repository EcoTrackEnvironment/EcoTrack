import "../styles/CardRecomendacaoSistema.css"
import { ToastContainer, toast } from 'react-toastify';

function RecomendacaoSistema({ icone, titulo, qtd_trechos_criticos, descricao_recomendacao, onClickAtivar }) {
    
    const textoSemPrefixo = descricao_recomendacao.replace("Recomendação:", "").trim();
    const notify = () => toast.success("Alocação realizada com sucesso!");

    const lidarComClique = () => {
        onClickAtivar;
        notify();
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
                    Alocar Equipe
                </button>
                <ToastContainer />
            </div>

        </div>
    )
}

export default RecomendacaoSistema;