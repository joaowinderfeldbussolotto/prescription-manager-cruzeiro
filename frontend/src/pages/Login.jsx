import { useState } from 'react'
import { useNavigate, useLocation, Navigate } from 'react-router-dom'
import { GoogleLogin } from '@react-oauth/google'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../api/client'
import Logo from '../components/Logo'

const GOOGLE_ENABLED = !!import.meta.env.VITE_GOOGLE_CLIENT_ID
const DEV_ENABLED = import.meta.env.VITE_DEV_AUTH !== 'false'

export default function Login() {
  const { user, loginGoogle, loginDev } = useAuth()
  const nav = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const from = location.state?.from?.pathname || '/'
  if (user) return <Navigate to={from} replace />

  async function handleGoogle(credentialResponse) {
    setError('')
    setBusy(true)
    try {
      await loginGoogle(credentialResponse.credential)
      nav(from, { replace: true })
    } catch (err) {
      // 403 traz "Email não autorizado" — mensagem clara, não erro genérico.
      setError(errorMessage(err, 'Não foi possível entrar com o Google.'))
    } finally {
      setBusy(false)
    }
  }

  async function handleDev(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await loginDev(email.trim())
      nav(from, { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Não foi possível entrar.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="card card-pad login-card">
        <Logo size={54} />
        <div className="brand-eyebrow" style={{ marginTop: '0.7rem' }}>
          Relojoaria e Ótica
        </div>
        <div className="wordmark">Cruzeiro</div>
        <p className="tagline">Cadastro de clientes e receitas ópticas</p>

        {error && <div className="alert alert-danger">{error}</div>}

        {GOOGLE_ENABLED && (
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <GoogleLogin
              onSuccess={handleGoogle}
              onError={() => setError('Falha na autenticação do Google.')}
              text="signin_with"
              shape="pill"
            />
          </div>
        )}

        {DEV_ENABLED && (
          <>
            {GOOGLE_ENABLED && <div className="divider">ou</div>}
            <form onSubmit={handleDev} className="stack" style={{ gap: '0.7rem' }}>
              <div className="field" style={{ textAlign: 'left' }}>
                <label htmlFor="dev-email">Acesso de desenvolvimento</label>
                <input
                  id="dev-email"
                  type="email"
                  required
                  placeholder="voce@exemplo.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
                <span className="hint">
                  O e-mail precisa estar na allowlist (coleção <code>usuarios</code>) e ativo.
                </span>
              </div>
              <button className="btn btn-primary btn-block" disabled={busy}>
                {busy ? 'Entrando…' : 'Entrar'}
              </button>
            </form>
          </>
        )}

        {!GOOGLE_ENABLED && !DEV_ENABLED && (
          <div className="alert alert-info">Nenhum método de login configurado.</div>
        )}
      </div>
    </div>
  )
}
