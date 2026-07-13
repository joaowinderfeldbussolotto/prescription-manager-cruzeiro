import { useState } from 'react'
import { Navigate, Link } from 'react-router-dom'
import { agente, errorMessage } from '../api/client'

// Guarda a mesma variável de padrão de EXTRACAO_IA_ENABLED em ReceitaForm.jsx.
const AGENTE_ENABLED = import.meta.env.VITE_AGENTE_ENABLED !== 'false'

// Atalhos que mandam a mesma mensagem que seriam digitadas à mão — o campo
// de texto livre abaixo aceita qualquer coisa, essas são só um ponto de
// partida rápido pra explorar o que o agente sabe fazer.
const SUGESTOES = [
  'Cadastra a cliente Maria Souza, CPF 111.222.333-44, telefone (48) 99911-2233, nascida em 12/04/1990',
  'Cadastra a cliente Maria Oliveira, telefone (48) 98822-1100',
  'Atualiza o telefone da Maria Souza para (48) 3333-0000',
  'Busca a cliente Maria',
  'Busca as receitas da Maria Souza',
  'Prepara uma receita para a Maria Souza',
]

// Casa links markdown [label](/caminho) que o agente inclui na resposta.
// Exige o href começar com "/" (rota interna) — evita linkificar uma URL
// externa que o modelo eventualmente alucine.
const LINK_RE = /\[([^\]]+)\]\((\/[^\s)]+)\)/g

function renderTexto(texto) {
  const partes = []
  let ultimoIndex = 0
  let match
  let key = 0
  LINK_RE.lastIndex = 0
  while ((match = LINK_RE.exec(texto)) !== null) {
    if (match.index > ultimoIndex) {
      partes.push(<span key={key++}>{texto.slice(ultimoIndex, match.index)}</span>)
    }
    partes.push(
      <Link key={key++} to={match[2]} className="btn btn-ghost btn-sm chat-link">
        {match[1]}
      </Link>,
    )
    ultimoIndex = match.index + match[0].length
  }
  if (ultimoIndex < texto.length) {
    partes.push(<span key={key++}>{texto.slice(ultimoIndex)}</span>)
  }
  return partes
}

function Bolha({ msg }) {
  const isUser = msg.autor === 'user'
  return (
    <div className={`chat-msg ${isUser ? 'user' : 'agente'}`}>
      <div className="chat-bubble">
        <p className="chat-texto">{renderTexto(msg.texto)}</p>
      </div>
    </div>
  )
}

export default function Agente() {
  const [mensagens, setMensagens] = useState([])
  const [enviando, setEnviando] = useState(false)
  const [texto, setTexto] = useState('')

  if (!AGENTE_ENABLED) {
    return <Navigate to="/" replace />
  }

  async function enviarMensagem(mensagem) {
    const msg = mensagem.trim()
    if (!msg || enviando) return
    setMensagens((prev) => [...prev, { autor: 'user', texto: msg }])
    setEnviando(true)
    try {
      const res = await agente.enviar(msg)
      setMensagens((prev) => [...prev, { autor: 'agente', texto: res.resposta }])
    } catch (err) {
      setMensagens((prev) => [...prev, { autor: 'agente', texto: errorMessage(err) }])
    } finally {
      setEnviando(false)
    }
  }

  function onSubmit(e) {
    e.preventDefault()
    const mensagem = texto
    setTexto('')
    enviarMensagem(mensagem)
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Agente</h1>
          <p className="subtitle">
            Converse em linguagem natural com o Assistente Virtual da Cruzeiro — cadastra,
            edita e busca clientes de verdade.
          </p>
        </div>
      </div>

      <div className="alert alert-info">
        As sugestões abaixo são atalhos — você também pode digitar livremente no campo de
        texto.
      </div>

      <div className="card chat-container">
        <div className="chat-messages">
          {mensagens.length === 0 && (
            <div className="empty">
              <p style={{ margin: 0 }}>Escolha uma sugestão ou digite uma mensagem para começar.</p>
            </div>
          )}
          {mensagens.map((m, i) => (
            <Bolha key={i} msg={m} />
          ))}
          {enviando && (
            <div className="chat-msg agente">
              <div className="chat-bubble">
                <span className="spinner" style={{ width: 16, height: 16 }} />
              </div>
            </div>
          )}
        </div>

        <div className="chat-sugestoes">
          {SUGESTOES.map((s) => (
            <button
              key={s}
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={enviando}
              onClick={() => enviarMensagem(s)}
            >
              {s}
            </button>
          ))}
        </div>

        <form className="chat-input-row" onSubmit={onSubmit}>
          <input
            type="text"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            disabled={enviando}
            placeholder="Digite sua mensagem…"
          />
          <button type="submit" className="btn btn-primary" disabled={enviando || !texto.trim()}>
            Enviar
          </button>
        </form>
      </div>
    </>
  )
}
