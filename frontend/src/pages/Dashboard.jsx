import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { dashboard, errorMessage } from '../api/client'

const CARDS = [
  { key: 'total_clientes', label: 'Clientes cadastrados' },
  { key: 'receitas_no_mes', label: 'Receitas cadastradas no mês' },
  { key: 'receitas_vencendo_30_dias', label: 'Receitas vencendo em 30 dias' },
]

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    dashboard
      .get()
      .then(setData)
      .catch((err) => setError(errorMessage(err)))
  }, [])

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <p className="subtitle">Visão geral do cadastro óptico</p>
        </div>
        <Link to="/clientes/novo" className="btn btn-primary">
          + Novo cliente
        </Link>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="stat-grid">
        {CARDS.map((c) => (
          <div key={c.key} className="card stat">
            <span className="accent" />
            <div className="label">{c.label}</div>
            <div className="value">{data ? data[c.key] : '—'}</div>
          </div>
        ))}
      </div>

      <div className="card card-pad">
        <div className="row-between">
          <div>
            <h3 style={{ margin: 0 }}>Comece por aqui</h3>
            <p className="muted" style={{ margin: '0.3rem 0 0' }}>
              Busque um cliente ou cadastre um novo para registrar receitas.
            </p>
          </div>
          <Link to="/clientes" className="btn btn-ghost">
            Ver clientes
          </Link>
        </div>
      </div>
    </>
  )
}
