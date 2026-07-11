import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { clientes, errorMessage } from '../api/client'
import { formatDate } from '../utils/format'

const LIMIT = 20

function SearchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" strokeLinecap="round" />
    </svg>
  )
}

export default function ClientesList() {
  const nav = useNavigate()
  const [busca, setBusca] = useState('')
  const [debounced, setDebounced] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(busca)
      setPage(1)
    }, 300)
    return () => clearTimeout(t)
  }, [busca])

  useEffect(() => {
    setLoading(true)
    clientes
      .list({ busca: debounced || undefined, page, limit: LIMIT })
      .then((res) => {
        setData(res)
        setError('')
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [debounced, page])

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1
  const items = data?.items || []

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Clientes</h1>
          <p className="subtitle">
            {data ? `${data.total} cliente(s)` : 'Carregando…'}
          </p>
        </div>
        <Link to="/clientes/novo" className="btn btn-primary">
          + Novo cliente
        </Link>
      </div>

      <div className="toolbar">
        <div className="search">
          <SearchIcon />
          <input
            placeholder="Buscar por nome ou telefone…"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {loading ? (
        <div className="center-screen">
          <div className="spinner" />
        </div>
      ) : items.length === 0 ? (
        <div className="card empty">
          <div className="wordmark">Cruzeiro</div>
          <p style={{ marginTop: '0.6rem' }}>
            {debounced ? 'Nenhum cliente encontrado para a busca.' : 'Nenhum cliente cadastrado ainda.'}
          </p>
          <Link to="/clientes/novo" className="btn btn-ghost">
            Cadastrar o primeiro
          </Link>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Telefone</th>
                <th>E-mail</th>
                <th>Receitas</th>
                <th>Cadastro</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} onClick={() => nav(`/clientes/${c.id}`)}>
                  <td style={{ fontWeight: 500 }}>{c.nome}</td>
                  <td>{c.telefone}</td>
                  <td className="muted">{c.email || '—'}</td>
                  <td>{c.total_receitas}</td>
                  <td className="muted">{formatDate(c.data_cadastro)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="pagination">
          <button
            className="btn btn-ghost btn-sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Anterior
          </button>
          <span>
            Página {page} de {totalPages}
          </span>
          <button
            className="btn btn-ghost btn-sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Próxima
          </button>
        </div>
      )}
    </>
  )
}
