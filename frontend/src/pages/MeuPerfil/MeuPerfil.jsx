import { useState } from 'react';
import { 
  FaUser, 
  FaEnvelope, 
  FaBriefcase, 
  FaLock, 
  FaCamera, 
  FaSave, 
  FaEye, 
  FaEyeSlash 
} from 'react-icons/fa';
import './MeuPerfil.css';

function MeuPerfil() {
  const [nome, setNome] = useState('João Silva');
  const [email, setEmail] = useState('joao.silva@ecotrack.com');
  const [cargo, setCargo] = useState('Operador de Rodovia');
  const [outroCargo, setOutroCargo] = useState('');
  
  // Estados para as senhas
  const [senhaAntiga, setSenhaAntiga] = useState('');
  const [novaSenha, setNovaSenha] = useState('');
  const [confirmarSenha, setConfirmarSenha] = useState('');

  // Estados para controlar a visibilidade dos campos de senha
  const [showSenhaAntiga, setShowSenhaAntiga] = useState(false);
  const [showNovaSenha, setShowNovaSenha] = useState(false);
  const [showConfirmarSenha, setShowConfirmarSenha] = useState(false);

  const cargoExibicao = cargo === 'Outro' ? (outroCargo || 'Outro') : cargo;

  const handleSalvarPerfil = (e) => {
    e.preventDefault();
    alert('Dados do perfil atualizados com sucesso!');
  };

  const handleAlterarSenha = (e) => {
    e.preventDefault();
    if (novaSenha !== confirmarSenha) {
      alert('As senhas digitadas não coincidem!');
      return;
    }
    alert('Senha alterada com sucesso!');
    setSenhaAntiga('');
    setNovaSenha('');
    setConfirmarSenha('');
  };

  return (
    <div className="perfil-container">
      <div className="perfil-header-title">
        <h2>Meu Perfil</h2>
        <p>Gerencie suas informações pessoais e credenciais de acesso</p>
      </div>

      <div className="perfil-content">
        {/* Cartão de Resumo do Usuário */}
        <div className="perfil-card avatar-card">
          <div className="avatar-wrapper">
            <div className="avatar-circle">
              {nome.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() || 'JS'}
            </div>
            <button className="avatar-edit-btn" title="Alterar Foto">
              <FaCamera />
            </button>
          </div>
          <h3>{nome}</h3>
          <span className="badge-cargo">{cargoExibicao}</span>
          <p className="email-text">{email}</p>
        </div>

        {/* Formulários de Edição */}
        <div className="perfil-forms-wrapper">
          <div className="perfil-card">
            <h3>Informações Pessoais</h3>
            <form onSubmit={handleSalvarPerfil} className="perfil-form">
              <div className="form-group">
                <label><FaUser /> Nome Completo</label>
                <input 
                  type="text" 
                  value={nome} 
                  onChange={(e) => setNome(e.target.value)} 
                  required 
                />
              </div>

              <div className="form-group">
                <label><FaEnvelope /> E-mail Corporativo</label>
                <input 
                  type="email" 
                  value={email} 
                  onChange={(e) => setEmail(e.target.value)} 
                  required 
                />
              </div>

              <div className="form-group">
                <label><FaBriefcase /> Função/Cargo</label>
                <select value={cargo} onChange={(e) => setCargo(e.target.value)}>
                  <option value="Operador de Rodovia">Operador de Rodovia</option>
                  <option value="Analista Ambiental">Analista Ambiental</option>
                  <option value="Gestor de Alocação">Gestor de Alocação</option>
                  <option value="Engenheiro de Infraestrutura">Engenheiro de Infraestrutura</option>
                  <option value="Outro">Outro</option>
                </select>
              </div>

              {cargo === 'Outro' && (
                <div className="form-group fade-in">
                  <label htmlFor="outroCargo">Especifique o cargo</label>
                  <input
                    type="text"
                    id="outroCargo"
                    placeholder="Digite sua função"
                    value={outroCargo}
                    onChange={(e) => setOutroCargo(e.target.value)}
                    required
                  />
                </div>
              )}

              <button type="submit" className="btn-salvar">
                <FaSave /> Salvar Alterações
              </button>
            </form>
          </div>

          <div className="perfil-card">
            <h3>Segurança da Conta</h3>
            <form onSubmit={handleAlterarSenha} className="perfil-form">
              <div className="form-group">
                <label><FaLock /> Senha Atual</label>
                <div className="password-input-wrapper">
                  <input 
                    type={showSenhaAntiga ? 'text' : 'password'} 
                    placeholder="••••••••" 
                    value={senhaAntiga} 
                    onChange={(e) => setSenhaAntiga(e.target.value)} 
                    required 
                  />
                  <button
                    type="button"
                    className="toggle-password-btn"
                    onClick={() => setShowSenhaAntiga(!showSenhaAntiga)}
                    title={showSenhaAntiga ? 'Ocultar senha' : 'Mostrar senha'}
                  >
                    {showSenhaAntiga ? <FaEyeSlash /> : <FaEye />}
                  </button>
                </div>
              </div>

              <div className="form-group">
                <label><FaLock /> Nova Senha</label>
                <div className="password-input-wrapper">
                  <input 
                    type={showNovaSenha ? 'text' : 'password'} 
                    placeholder="••••••••" 
                    value={novaSenha} 
                    onChange={(e) => setNovaSenha(e.target.value)} 
                    required 
                  />
                  <button
                    type="button"
                    className="toggle-password-btn"
                    onClick={() => setShowNovaSenha(!showNovaSenha)}
                    title={showNovaSenha ? 'Ocultar senha' : 'Mostrar senha'}
                  >
                    {showNovaSenha ? <FaEyeSlash /> : <FaEye />}
                  </button>
                </div>
              </div>

              <div className="form-group">
                <label><FaLock /> Confirmar Nova Senha</label>
                <div className="password-input-wrapper">
                  <input 
                    type={showConfirmarSenha ? 'text' : 'password'} 
                    placeholder="••••••••" 
                    value={confirmarSenha} 
                    onChange={(e) => setConfirmarSenha(e.target.value)} 
                    required 
                  />
                  <button
                    type="button"
                    className="toggle-password-btn"
                    onClick={() => setShowConfirmarSenha(!showConfirmarSenha)}
                    title={showConfirmarSenha ? 'Ocultar senha' : 'Mostrar senha'}
                  >
                    {showConfirmarSenha ? <FaEyeSlash /> : <FaEye />}
                  </button>
                </div>
              </div>

              <button type="submit" className="btn-salvar btn-secundario">
                Atualizar Senha
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MeuPerfil;