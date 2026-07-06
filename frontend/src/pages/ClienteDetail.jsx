import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { clientes, errorMessage } from '../api/client'
import { formatDate } from '../utils/format'
import ValidadeBadge from '../components/ValidadeBadge'

export default function ClienteDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const location = useLocation()
  const [cliente, setCliente] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showSuccess, setShowSuccess] = useState(Boolean(location.state?.justCreated))

  useEffect(() => {
    setLoading(true)
    clientes
      .get(id)
      .then(setCliente)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (!location.state?.justCreated) return
    // limpa o state do history pra não reexibir o aviso num refresh da página
    nav(location.pathname, { replace: true, state: {} })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!showSuccess) return
    const t = setTimeout(() => setShowSuccess(false), 6000)
    return () => clearTimeout(t)
  }, [showSuccess])

  async function handleDelete() {
    if (!window.confirm('Remover este cliente? Se houver receitas, ele será arquivado.')) return
    try {
      await clientes.remove(id)
      nav('/clientes')
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  if (loading) {
    return (
      <div className="center-screen">
        <div className="spinner" />
      </div>
    )
  }
  if (error && !cliente) return <div className="alert alert-danger">{error}</div>
  if (!cliente) return null

  const receitas = cliente.receitas || []

  return (
    <>
      <button
        type="button"
        className="btn btn-ghost btn-sm back-link"
        onClick={() => nav('/clientes')}
      >
        ← Voltar para clientes
      </button>

      {showSuccess && (
        <div className="alert alert-success">
          <span>✓ Cliente cadastrado com sucesso.</span>
          <button type="button" onClick={() => setShowSuccess(false)} aria-label="Fechar aviso">
            ✕
          </button>
        </div>
      )}

      <div className="page-head">
        <div>
          <p className="subtitle" style={{ margin: 0 }}>
            <Link to="/clientes">Clientes</Link> / detalhe
          </p>
          <h1 style={{ marginTop: '0.2rem' }}>{cliente.nome}</h1>
        </div>
        <div style={{ display: 'flex', gap: '0.6rem' }}>
          <Link to={`/clientes/${id}/editar`} className="btn btn-ghost">
            Editar
          </Link>
          <button className="btn btn-danger" onClick={handleDelete}>
            Remover
          </button>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="stack">
        <div className="card card-pad">
          <dl className="meta-list">
            <dt>Telefone</dt>
            <dd>{cliente.telefone}</dd>
            <dt>CPF</dt>
            <dd>{cliente.cpf || '—'}</dd>
            <dt>E-mail</dt>
            <dd>{cliente.email || '—'}</dd>
            <dt>Nascimento</dt>
            <dd>{formatDate(cliente.data_nascimento)}</dd>
            <dt>Endereço</dt>
            <dd>{cliente.endereco || '—'}</dd>
            <dt>Cadastro</dt>
            <dd>{formatDate(cliente.data_cadastro)}</dd>
          </dl>
        </div>

        <div>
          <div className="row-between" style={{ marginBottom: '0.9rem' }}>
            <h2 style={{ margin: 0 }}>Receitas</h2>
            <Link to={`/clientes/${id}/receitas/nova`} className="btn btn-primary">
              + Nova receita
            </Link>
          </div>

          {receitas.length === 0 ? (
            <div className="card empty">
              <p>Nenhuma receita registrada para este cliente.</p>
              <Link to={`/clientes/${id}/receitas/nova`} className="btn btn-ghost">
                Registrar receita
              </Link>
            </div>
          ) : (
            <div className="timeline">
              {receitas.map((r) => (
                <div key={r.id} className="card rx-card" onClick={() => nav(`/receitas/${r.id}`)}>
                  <div className="rx-main">
                    <strong>Emitida em {formatDate(r.data_emissao)}</strong>
                    <span className="rx-dates">
                      Validade: {formatDate(r.validade)}
                      {r.medico_nome ? ` · Dr(a). ${r.medico_nome}` : ''}
                      {r.tem_imagem ? ' · 📎 imagem' : ''}
                    </span>
                  </div>
                  <ValidadeBadge validade={r.validade} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
