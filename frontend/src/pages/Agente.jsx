import { useState } from 'react'
import { Navigate, Link } from 'react-router-dom'
import { agente, errorMessage } from '../api/client'

// Guarda a mesma variável de padrão de EXTRACAO_IA_ENABLED em ReceitaForm.jsx.
const AGENTE_ENABLED = import.meta.env.VITE_AGENTE_ENABLED !== 'false'

// Estas frases precisam bater EXATAMENTE com as chaves de CENARIOS_MOCK em
// backend/app/schemas/agente.py — ver o comentário lá explicando por quê
// (nesta fase, sem LLM, a interpretação é por correspondência exata; o texto
// livre fica pra quando um LLM real entrar no lugar do lookup).
const SUGESTOES = [
  'Cadastra a cliente Maria Souza, CPF 111.222.333-44, telefone (48) 99911-2233, nascida em 12/04/1990',
  'Cadastra a cliente Maria Oliveira, telefone (48) 98822-1100',
  'Atualiza o telefone da Maria Souza para (48) 3333-0000',
  'Busca a cliente Maria',
  'Busca as receitas da Maria Souza',
  'Prepara uma receita para a Maria Souza',
]

function Bolha({ msg }) {
  const isUser = msg.autor === 'user'
  return (
    <div className={`chat-msg ${isUser ? 'user' : 'agente'}`}>
      <div className="chat-bubble">
        <p style={{ margin: 0 }}>{msg.texto}</p>

        {msg.acoes?.length > 0 && (
          <div className="chat-acoes">
            {msg.acoes.map((a, i) => (
              <div key={i} className="chat-acao">
                <div className="chat-acao-tool">🔧 {a.tool}</div>
                <pre>{JSON.stringify(a.argumentos, null, 2)}</pre>
                {Object.keys(a.resultado || {}).length > 0 && (
                  <>
                    <div className="chat-acao-tool">↳ resultado</div>
                    <pre>{JSON.stringify(a.resultado, null, 2)}</pre>
                  </>
                )}
              </div>
            ))}
          </div>
        )}

        {msg.links?.length > 0 && (
          <div className="chat-links">
            {msg.links.map((l, i) => (
              <Link key={i} to={l.href} className="btn btn-ghost btn-sm">
                {l.label}
              </Link>
            ))}
          </div>
        )}

        {msg.aviso && <div className="alert alert-info chat-aviso">{msg.aviso}</div>}
      </div>
    </div>
  )
}

export default function Agente() {
  const [mensagens, setMensagens] = useState([])
  const [enviando, setEnviando] = useState(false)

  if (!AGENTE_ENABLED) {
    return <Navigate to="/" replace />
  }

  async function enviarSugestao(texto) {
    if (enviando) return
    setMensagens((prev) => [...prev, { autor: 'user', texto }])
    setEnviando(true)
    try {
      const res = await agente.enviar(texto)
      setMensagens((prev) => [
        ...prev,
        {
          autor: 'agente',
          texto: res.resposta,
          acoes: res.acoes,
          links: res.links,
          aviso: res.aviso,
        },
      ])
    } catch (err) {
      setMensagens((prev) => [...prev, { autor: 'agente', texto: errorMessage(err) }])
    } finally {
      setEnviando(false)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Agente</h1>
          <p className="subtitle">
            Converse em linguagem natural com o agente — cadastra, edita e busca clientes de verdade.
          </p>
        </div>
      </div>

      <div className="alert alert-info">
        Fase mock: a interpretação da frase é simulada (sem IA real) — escolha uma das
        sugestões abaixo. As ações no banco de dados são reais.
      </div>

      <div className="card chat-container">
        <div className="chat-messages">
          {mensagens.length === 0 && (
            <div className="empty">
              <p style={{ margin: 0 }}>Escolha uma sugestão abaixo para começar.</p>
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
              onClick={() => enviarSugestao(s)}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="chat-input-row">
          <input
            type="text"
            disabled
            placeholder="Em breve: digite livremente — o agente vai interpretar com IA real"
          />
          <button type="button" className="btn btn-primary" disabled>
            Enviar
          </button>
        </div>
      </div>
    </>
  )
}
