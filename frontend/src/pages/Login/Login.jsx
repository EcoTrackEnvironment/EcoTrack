import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import logoEcoTrack from '../../components/Header/assets/logo_ecotrack.png';
import './Login.css';

function Login() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [nome, setNome] = useState('');
  const [cargo, setCargo] = useState('Operador de Rodovia');
  const [outroCargo, setOutroCargo] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    alert(
      isRegister
        ? 'Cadastro demonstrativo: nenhuma solicitação foi enviada.'
        : 'Acesso demonstrativo: este protótipo ainda não autentica usuários.'
    );
    navigate('/dashboard');
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <div className="logo-brand">
            <img 
              src={logoEcoTrack} 
              alt="Logo EcoTrack" 
              className="login-logo-img"
              onError={(e) => {
                e.target.onerror = null; 
              }}
            />
            <h2>EcoTrack</h2>
          </div>
          <p className="subtitle">
            {isRegister ? 'Cadastro de Novo Colaborador' : 'Acesso ao Portal Operacional'}
          </p>
          <p className="subtitle" role="status">
            Modo demonstração: acesso e cadastro ainda não são autenticados pelo servidor.
          </p>
        </div>

        {/* Formulário */}
        <form className="login-form" onSubmit={handleSubmit}>
          {isRegister && (
            <>
              <div className="form-group">
                <label htmlFor="nome">Nome Completo</label>
                <input
                  type="text"
                  id="nome"
                  placeholder="Ex: João Silva"
                  value={nome}
                  onChange={(e) => setNome(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="cargo">Função/Cargo</label>
                <select
                  id="cargo"
                  value={cargo}
                  onChange={(e) => setCargo(e.target.value)}
                >
                  <option value="Operador de Rodovia">Operador de Rodovia</option>
                  <option value="Analista Ambiental">Analista Ambiental</option>
                  <option value="Gestor de Alocação">Gestor de Alocação</option>
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
            </>
          )}

          <div className="form-group">
            <label htmlFor="email">E-mail Corporativo</label>
            <input
              type="email"
              id="email"
              placeholder="funcionario@ecotrack.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Senha</label>
            <div className="password-input-wrapper">
              <input
                type={showPassword ? 'text' : 'password'}
                id="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="toggle-password-btn"
                onClick={() => setShowPassword(!showPassword)}
                title={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
              >
                {showPassword ? (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          {!isRegister && (
            <div className="form-options">
              <a href="#esqueceu" onClick={(e) => e.preventDefault()}>Esqueceu a senha?</a>
            </div>
          )}

          <button type="submit" className="btn-primary">
            {isRegister ? 'Solicitar Acesso' : 'Entrar'}
          </button>
        </form>

        {/* Alternar entre Login / Primeiro Acesso */}
        <div className="login-footer">
          <p>
            {isRegister ? 'Já possui cadastro? ' : 'Primeiro acesso na plataforma? '}
            <button
              type="button"
              className="btn-toggle"
              onClick={() => {
                setIsRegister(!isRegister);
                setCargo('Operador de Rodovia');
              }}
            >
              {isRegister ? 'Fazer Login' : 'Cadastrar-se'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}

export default Login;
