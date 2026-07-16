import { useState } from 'react'
import { Navigate, Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
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
  'Agenda um acompanhamento pra ligar pra Maria Souza dia 20/08/2026 e oferecer desconto',
  'Quais são os meus acompanhamentos pendentes?',
]

// Renderer customizado pro link markdown ([label](/caminho)) que as tools
// do agente incluem na resposta. Rota interna (começa com "/") vira
// navegação SPA via react-router; qualquer outra URL abre em nova aba
// (defensivo — o prompt já instrui só linkar rotas internas).
function MarkdownLink({ href, children }) {
  if (href?.startsWith('/')) {
    return (
      <Link to={href} className="btn btn-ghost btn-sm chat-link">
        {children}
      </Link>
    )
  }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  )
}

// Identifica esta "aba/carregamento de página" do chat — não confundir com
// a sessão de autenticação (cookie de login). Gerado uma vez por mount do
// componente: um F5 remonta tudo do zero, então o backend passa a tratar
// como uma conversa nova (memória multi-turn + agrupamento no Langfuse).
// Usa crypto.getRandomValues() em vez de crypto.randomUUID() porque este
// último só funciona em contexto seguro (HTTPS/localhost) — a instância
// atual em produção roda em HTTP puro.
function gerarSessionId() {
  const bytes = crypto.getRandomValues(new Uint32Array(4))
  return Array.from(bytes, (n) => n.toString(16)).join('-')
}

function Bolha({ msg }) {
  const isUser = msg.autor === 'user'
  return (
    <div className={`chat-msg ${isUser ? 'user' : 'agente'}`}>
      <div className="chat-bubble">
        <div className="chat-texto">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: MarkdownLink }}>
            {msg.texto}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  )
}

export default function Agente() {
  const [mensagens, setMensagens] = useState([])
  const [enviando, setEnviando] = useState(false)
  const [texto, setTexto] = useState('')
  const [sessionId] = useState(gerarSessionId)

  if (!AGENTE_ENABLED) {
    return <Navigate to="/" replace />
  }

  async function enviarMensagem(mensagem) {
    const msg = mensagem.trim()
    if (!msg || enviando) return
    setMensagens((prev) => [...prev, { autor: 'user', texto: msg }])
    setEnviando(true)
    try {
      const res = await agente.enviar(msg, sessionId)
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
