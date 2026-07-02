import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { clientes, errorMessage } from '../api/client'

const EMPTY = {
  nome: '',
  telefone: '',
  cpf: '',
  email: '',
  data_nascimento: '',
  endereco: '',
}

export default function ClienteForm() {
  const { id } = useParams()
  const isEdit = Boolean(id)
  const nav = useNavigate()
  const [form, setForm] = useState(EMPTY)
  const [loading, setLoading] = useState(isEdit)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isEdit) return
    clientes
      .get(id)
      .then((c) =>
        setForm({
          nome: c.nome || '',
          telefone: c.telefone || '',
          cpf: c.cpf || '',
          email: c.email || '',
          data_nascimento: c.data_nascimento ? String(c.data_nascimento).slice(0, 10) : '',
          endereco: c.endereco || '',
        }),
      )
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [id, isEdit])

  function set(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    const payload = {
      nome: form.nome.trim(),
      telefone: form.telefone.trim(),
      cpf: form.cpf.trim() || null,
      email: form.email.trim() || null,
      data_nascimento: form.data_nascimento || null,
      endereco: form.endereco.trim() || null,
    }
    try {
      const saved = isEdit ? await clientes.update(id, payload) : await clientes.create(payload)
      nav(`/clientes/${saved.id}`)
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="center-screen">
        <div className="spinner" />
      </div>
    )
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{isEdit ? 'Editar cliente' : 'Novo cliente'}</h1>
          <p className="subtitle">Dados de cadastro</p>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <form className="card card-pad" onSubmit={handleSubmit}>
        <div className="form-grid">
          <div className="field col-span-2">
            <label htmlFor="nome">
              Nome <span className="req">*</span>
            </label>
            <input id="nome" required value={form.nome} onChange={set('nome')} />
          </div>

          <div className="field">
            <label htmlFor="telefone">
              Telefone <span className="req">*</span>
            </label>
            <input id="telefone" required value={form.telefone} onChange={set('telefone')} />
          </div>

          <div className="field">
            <label htmlFor="cpf">CPF</label>
            <input
              id="cpf"
              value={form.cpf}
              onChange={set('cpf')}
              placeholder="000.000.000-00"
            />
            <span className="hint">Validação de formato apenas.</span>
          </div>

          <div className="field">
            <label htmlFor="email">E-mail</label>
            <input id="email" type="email" value={form.email} onChange={set('email')} />
          </div>

          <div className="field">
            <label htmlFor="nascimento">Data de nascimento</label>
            <input
              id="nascimento"
              type="date"
              value={form.data_nascimento}
              onChange={set('data_nascimento')}
            />
          </div>

          <div className="field col-span-2">
            <label htmlFor="endereco">Endereço</label>
            <textarea id="endereco" value={form.endereco} onChange={set('endereco')} />
          </div>
        </div>

        <div className="form-actions">
          <Link to={isEdit ? `/clientes/${id}` : '/clientes'} className="btn btn-ghost">
            Cancelar
          </Link>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? 'Salvando…' : 'Salvar'}
          </button>
        </div>
      </form>
    </>
  )
}
