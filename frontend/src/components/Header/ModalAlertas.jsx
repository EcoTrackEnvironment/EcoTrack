import { FaExclamationTriangle, FaInfoCircle, FaCheckCircle } from "react-icons/fa";

function ModalAlertas({ alertas, marcarTodosComoLidos }) {
  const naoLidos = alertas.filter((a) => !a.lido).length;

  return (
    <div className="notif-dropdown">
      <div className="notif-header">
        <strong>Alertas do Sistema</strong>
        {naoLidos > 0 && (
          <button className="btn-limpar" onClick={marcarTodosComoLidos}>
            Marcar lidos
          </button>
        )}
      </div>

      <div className="notif-list">
        {alertas.map((item) => (
          <div
            key={item.id}
            className={`notif-item ${!item.lido ? "nao-lido" : ""}`}
          >
            <div className={`notif-icon ${item.tipo}`}>
              {item.tipo === "critico" && <FaExclamationTriangle />}
              {item.tipo === "alerta" && <FaInfoCircle />}
              {item.tipo === "info" && <FaCheckCircle />}
            </div>
            <div className="notif-text">
              <div className="notif-title-row">
                <span className="notif-titulo">{item.titulo}</span>
                <span className="notif-tempo">{item.tempo}</span>
              </div>
              <p className="notif-mensagem">{item.mensagem}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ModalAlertas;