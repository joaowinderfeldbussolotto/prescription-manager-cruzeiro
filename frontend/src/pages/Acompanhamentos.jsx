import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { acompanhamentos, errorMessage } from '../api/client'
import { formatDate } from '../utils/format'

const LIMIT = 20

const TIPO_LABEL = {
  ligar: 'Ligar',
  email: 'E-mail',
  sms: 'SMS',
  visita: 'Visita',
  outro: 'Outro',
}

export default function Acompanhamentos() {
  const [filtro, setFiltro] = useState('pendentes')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [concluindo, setConcluindo] = useState(null)

  function carregar() {
    setLoading(true)
    acompanhamentos
      .list({ filtro, page, limit: LIMIT })
      .then((res) => {
        setData(res)
        setError('')
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(carregar, [filtro, page])

  function onFiltroChange(novoFiltro) {
    setFiltro(novoFiltro)
    setPage(1)
  }

  async function marcarConcluido(id) {
    setConcluindo(id)
    try {
      await acompanhamentos.concluir(id)
      carregar()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setConcluindo(null)
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1
  const items = data?.items || []

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Acompanhamentos</h1>
          <p className="subtitle">
            Seus lembretes e follow-ups agendados pelo Agente — {data ? `${data.total} registro(s)` : 'carregando…'}
          </p>
        </div>
      </div>

      <div className="toolbar">
        <select value={filtro} onChange={(e) => onFiltroChange(e.target.value)}>
          <option value="pendentes">Pendentes</option>
          <option value="concluido">Concluídos</option>
          <option value="todos">Todos</option>
        </select>
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
            {filtro === 'pendentes'
              ? 'Nenhum acompanhamento pendente. Peça pro Agente agendar um.'
              : 'Nenhum acompanhamento encontrado.'}
          </p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Data</th>
                <th>Cliente</th>
                <th>Tipo</th>
                <th>Descrição</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id}>
                  <td className="muted">{formatDate(a.data_agendada)}</td>
                  <td style={{ fontWeight: 500 }}>
                    <Link to={`/clientes/${a.cliente_id}`}>{a.cliente_nome}</Link>
                  </td>
                  <td>{TIPO_LABEL[a.tipo] || a.tipo}</td>
                  <td>{a.descricao}</td>
                  <td>
                    {a.concluido ? (
                      <span className="badge badge-ok">Concluído</span>
                    ) : (
                      <span className="badge badge-warn">Pendente</span>
                    )}
                  </td>
                  <td>
                    {!a.concluido && (
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        disabled={concluindo === a.id}
                        onClick={() => marcarConcluido(a.id)}
                      >
                        {concluindo === a.id ? 'Marcando…' : 'Marcar concluído'}
                      </button>
                    )}
                  </td>
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
