import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { receitas, clientes, errorMessage } from '../api/client'
import { formatDate, formatGrau, formatEixo, formatDp } from '../utils/format'
import ValidadeBadge from '../components/ValidadeBadge'

export default function ReceitaView() {
  const { id } = useParams()
  const nav = useNavigate()
  const location = useLocation()
  const [receita, setReceita] = useState(null)
  const [cliente, setCliente] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showSuccess, setShowSuccess] = useState(Boolean(location.state?.justCreated))

  useEffect(() => {
    let active = true
    setLoading(true)
    receitas
      .get(id)
      .then((r) => {
        if (!active) return
        setReceita(r)
        return clientes.get(r.cliente_id).then((c) => active && setCliente(c))
      })
      .catch((err) => active && setError(errorMessage(err)))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
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
    if (!window.confirm('Remover esta receita? A ação não pode ser desfeita.')) return
    try {
      await receitas.remove(id)
      nav(receita ? `/clientes/${receita.cliente_id}` : '/clientes')
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
  if (error && !receita) return <div className="alert alert-danger">{error}</div>
  if (!receita) return null

  const isPdf = (receita.imagem_key || '').endsWith('.pdf')

  return (
    <>
      <button
        type="button"
        className="btn btn-ghost btn-sm back-link"
        onClick={() => nav(`/clientes/${receita.cliente_id}`)}
      >
        ← Voltar para o cliente
      </button>

      {showSuccess && (
        <div className="alert alert-success">
          <span>✓ Receita cadastrada com sucesso.</span>
          <button type="button" onClick={() => setShowSuccess(false)} aria-label="Fechar aviso">
            ✕
          </button>
        </div>
      )}

      <div className="page-head">
        <div>
          <p className="subtitle" style={{ margin: 0 }}>
            <Link to="/clientes">Clientes</Link> /{' '}
            {cliente ? (
              <Link to={`/clientes/${receita.cliente_id}`}>{cliente.nome}</Link>
            ) : (
              <Link to={`/clientes/${receita.cliente_id}`}>cliente</Link>
            )}{' '}
            / receita
          </p>
          <h1 style={{ marginTop: '0.2rem', display: 'flex', gap: '0.7rem', alignItems: 'center' }}>
            Receita <ValidadeBadge validade={receita.validade} />
          </h1>
        </div>
        <div style={{ display: 'flex', gap: '0.6rem' }}>
          <Link to={`/receitas/${id}/editar`} className="btn btn-ghost">
            Editar
          </Link>
          <button className="btn btn-danger" onClick={handleDelete}>
            Remover
          </button>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="rx-view">
        {/* Documento (imagem) */}
        <div className="rx-image">
          {receita.imagem_url ? (
            isPdf ? (
              <div className="placeholder">
                <p>📄 Documento em PDF</p>
                <a className="btn btn-ghost btn-sm" href={receita.imagem_url} target="_blank" rel="noreferrer">
                  Abrir PDF
                </a>
              </div>
            ) : (
              <a href={receita.imagem_url} target="_blank" rel="noreferrer">
                <img src={receita.imagem_url} alt="Receita" />
              </a>
            )
          ) : (
            <div className="placeholder">Sem imagem anexada</div>
          )}
        </div>

        {/* Metadados */}
        <div className="stack">
          <div className="card card-pad">
            <h3>Datas &amp; médico</h3>
            <dl className="meta-list">
              <dt>Emissão</dt>
              <dd>{formatDate(receita.data_emissao)}</dd>
              <dt>Validade</dt>
              <dd>{formatDate(receita.validade)}</dd>
              <dt>Médico</dt>
              <dd>{receita.medico_nome || '—'}</dd>
              <dt>CRM</dt>
              <dd>{receita.medico_crm || '—'}</dd>
            </dl>
          </div>

          <div className="card card-pad">
            <h3>Graus</h3>
            <div className="table-wrap" style={{ border: 'none' }}>
              <table className="grau-table">
                <thead>
                  <tr>
                    <th>Olho</th>
                    <th>Esférico</th>
                    <th>Cilíndrico</th>
                    <th>Eixo</th>
                    <th>Adição</th>
                  </tr>
                </thead>
                <tbody>
                  <tr style={{ cursor: 'default' }}>
                    <td>OD</td>
                    <td>{formatGrau(receita.od_esferico)}</td>
                    <td>{formatGrau(receita.od_cilindrico)}</td>
                    <td>{formatEixo(receita.od_eixo)}</td>
                    <td>{formatGrau(receita.od_adicao)}</td>
                  </tr>
                  <tr style={{ cursor: 'default' }}>
                    <td>OE</td>
                    <td>{formatGrau(receita.oe_esferico)}</td>
                    <td>{formatGrau(receita.oe_cilindrico)}</td>
                    <td>{formatEixo(receita.oe_eixo)}</td>
                    <td>{formatGrau(receita.oe_adicao)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <dl className="meta-list" style={{ marginTop: '1rem' }}>
              <dt>DP</dt>
              <dd>{formatDp(receita.dp)}</dd>
              <dt>DP longe</dt>
              <dd>{formatDp(receita.dp_longe)}</dd>
              <dt>DP perto</dt>
              <dd>{formatDp(receita.dp_perto)}</dd>
            </dl>
          </div>

          {receita.observacoes && (
            <div className="card card-pad">
              <h3>Observações</h3>
              <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{receita.observacoes}</p>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
