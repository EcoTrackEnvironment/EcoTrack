import { useState } from 'react';
import { FaMoon, FaSun, FaBell, FaSync, FaSave } from 'react-icons/fa';
import './Configuracoes.css';

function Configuracoes() {
  const [selectedTheme, setSelectedTheme] = useState('light');
  const [notifEmail, setNotifEmail] = useState(true);
  const [notifAlertas, setNotifAlertas] = useState(true);
  const [intervaloAtualizacao, setIntervaloAtualizacao] = useState('30');

  const handleSalvar = (e) => {
    e.preventDefault();
    alert('Configurações salvas com sucesso!');
  };

  return (
    <div className="config-container">
      <div className="config-header-title">
        <h2>Configurações do Sistema</h2>
        <p>Personalize a aparência, notificações e preferências da plataforma</p>
      </div>

      <form onSubmit={handleSalvar} className="config-content">

        <div className="config-card">
          <h3><FaSun /> Aparência e Tema</h3>
          <p className="card-description">Escolha a combinação de cores de sua preferência para a interface</p>
          
          <div className="theme-options">
            <button
              type="button"
              className={`theme-btn ${selectedTheme === 'light' ? 'active' : ''}`}
              onClick={() => setSelectedTheme('light')}
            >
              <FaSun className="theme-icon" />
              <div>
                <strong>Modo Claro</strong>
                <span>Ideal para ambientes bem iluminados</span>
              </div>
            </button>

            <button
              type="button"
              className={`theme-btn ${selectedTheme === 'dark' ? 'active' : ''}`}
              onClick={() => setSelectedTheme('dark')}
            >
              <FaMoon className="theme-icon" />
              <div>
                <strong>Modo Escuro</strong>
                <span>Reduz a fadiga visual durante a noite</span>
              </div>
            </button>
          </div>
        </div>

        <div className="config-card">
          <h3><FaBell /> Notificações</h3>
          <p className="card-description">Gerencie os alertas e mensagens recebidas no portal</p>
          
          <div className="toggle-list">
            <label className="toggle-item">
              <div>
                <strong>Alertas do Sistema</strong>
                <span>Receba notificações sobre desvios e trechos críticos</span>
              </div>
              <input 
                type="checkbox" 
                checked={notifAlertas} 
                onChange={(e) => setNotifAlertas(e.target.checked)} 
              />
            </label>

            <label className="toggle-item">
              <div>
                <strong>Notificações por e-mail</strong>
                <span>Resumos semanais dos indicadores ambientais</span>
              </div>
              <input 
                type="checkbox" 
                checked={notifEmail} 
                onChange={(e) => setNotifEmail(e.target.checked)} 
              />
            </label>
          </div>
        </div>

        <div className="config-card">
          <h3><FaSync /> Atualização da Dashboard</h3>
          <p className="card-description">Frequência com que os dados são sincronizados</p>
          
          <div className="form-group">
            <label htmlFor="frequencia">Intervalo de Sincronização</label>
            <select 
              id="frequencia"
              value={intervaloAtualizacao} 
              onChange={(e) => setIntervaloAtualizacao(e.target.value)}
            >
              <option value="15">A cada 15 segundos (tempo real)</option>
              <option value="30">A cada 30 segundos (recomendado)</option>
              <option value="60">A cada 1 minuto</option>
              <option value="0">Manual (sem atualização automática)</option>
            </select>
          </div>
        </div>

        <button type="submit" className="btn-salvar-config">
          <FaSave /> Salvar Configurações
        </button>
      </form>
    </div>
  );
}

export default Configuracoes;