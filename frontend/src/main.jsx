import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { AuthProvider } from './context/AuthContext'
import App from './App'
import './index.css'

// Client ID do Google (opcional em dev — sem ele, usa-se o login de
// desenvolvimento). Só montamos o GoogleOAuthProvider quando há client id
// configurado, evitando que a tela de login quebre no fluxo dev padrão.
const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''

const tree = (
  <BrowserRouter>
    <AuthProvider>
      <App />
    </AuthProvider>
  </BrowserRouter>
)

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {clientId ? <GoogleOAuthProvider clientId={clientId}>{tree}</GoogleOAuthProvider> : tree}
  </React.StrictMode>,
)
