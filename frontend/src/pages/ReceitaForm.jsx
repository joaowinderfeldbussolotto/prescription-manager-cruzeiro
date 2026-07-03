import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { receitas, uploads, uploadToStorage, errorMessage } from '../api/client'

// data de hoje em ISO (YYYY-MM-DD), sem shift de fuso
function todayISO() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

// +12 meses espelhando a regra do backend (29/02 -> 28/02).
function plus12Months(iso) {
  if (!iso) return ''
  const [y, m, d] = iso.split('-').map(Number)
  const ny = y + 1
  const daysInMonth = new Date(ny, m, 0).getDate()
  const nd = Math.min(d, daysInMonth)
  const pad = (n) => String(n).padStart(2, '0')
  return `${ny}-${pad(m)}-${pad(nd)}`
}

const num = (v) => (v === '' || v === null || v === undefined ? null : Number(v))
const int = (v) => (v === '' || v === null || v === undefined ? null : parseInt(v, 10))

const BASE = {
  data_emissao: '',
  validade: '',
  medico_nome: '',
  medico_crm: '',
  od_esferico: '',
  od_cilindrico: '',
  od_eixo: '',
  od_adicao: '',
  oe_esferico: '',
  oe_cilindrico: '',
  oe_eixo: '',
  oe_adicao: '',
  dp: '',
  dp_longe: '',
  dp_perto: '',
  observacoes: '',
}

function OlhoFields({ prefix, label, form, set }) {
  return (
    <div>
      <h3 style={{ color: 'var(--gold-700)', fontSize: '0.9rem', letterSpacing: '0.04em' }}>
        {label}
      </h3>
      <div className="form-grid">
        <div className="field">
          <label>Esférico</label>
          <input
            type="number"
            step="0.25"
            value={form[`${prefix}_esferico`]}
            onChange={set(`${prefix}_esferico`)}
            placeholder="-2.50"
          />
        </div>
        <div className="field">
          <label>Cilíndrico</label>
          <input
            type="number"
            step="0.25"
            value={form[`${prefix}_cilindrico`]}
            onChange={set(`${prefix}_cilindrico`)}
          />
        </div>
        <div className="field">
          <label>Eixo (0–180)</label>
          <input
            type="number"
            min="0"
            max="180"
            step="1"
            value={form[`${prefix}_eixo`]}
            onChange={set(`${prefix}_eixo`)}
          />
        </div>
        <div className="field">
          <label>Adição</label>
          <input
            type="number"
            step="0.25"
            value={form[`${prefix}_adicao`]}
            onChange={set(`${prefix}_adicao`)}
          />
        </div>
      </div>
    </div>
  )
}

export default function ReceitaForm() {
  const { clienteId, id } = useParams()
  const isEdit = Boolean(id)
  const nav = useNavigate()
  const fileRef = useRef(null)

  // Na criação, a emissão já vem preenchida com a data de hoje (editável).
  const [form, setForm] = useState(() =>
    isEdit ? BASE : { ...BASE, data_emissao: todayISO(), validade: plus12Months(todayISO()) },
  )
  const [validadeTouched, setValidadeTouched] = useState(false)
  // Só a imagem aparece por padrão; os demais campos ficam atrás deste toggle.
  const [showDetails, setShowDetails] = useState(isEdit)
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null) // {url, isPdf}
  const [existingKey, setExistingKey] = useState(null)
  const [loading, setLoading] = useState(isEdit)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [backTo, setBackTo] = useState(clienteId ? `/clientes/${clienteId}` : '/clientes')

  useEffect(() => {
    if (!isEdit) return
    receitas
      .get(id)
      .then((r) => {
        setForm({
          data_emissao: String(r.data_emissao).slice(0, 10),
          validade: String(r.validade).slice(0, 10),
          medico_nome: r.medico_nome || '',
          medico_crm: r.medico_crm || '',
          od_esferico: r.od_esferico ?? '',
          od_cilindrico: r.od_cilindrico ?? '',
          od_eixo: r.od_eixo ?? '',
          od_adicao: r.od_adicao ?? '',
          oe_esferico: r.oe_esferico ?? '',
          oe_cilindrico: r.oe_cilindrico ?? '',
          oe_eixo: r.oe_eixo ?? '',
          oe_adicao: r.oe_adicao ?? '',
          dp: r.dp ?? '',
          dp_longe: r.dp_longe ?? '',
          dp_perto: r.dp_perto ?? '',
          observacoes: r.observacoes || '',
        })
        setValidadeTouched(true)
        setExistingKey(r.imagem_key || null)
        if (r.imagem_url) {
          setPreview({ url: r.imagem_url, isPdf: (r.imagem_key || '').endsWith('.pdf') })
        }
        setBackTo(`/receitas/${id}`)
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [id, isEdit])

  function set(field) {
    return (e) => {
      const value = e.target.value
      setForm((f) => {
        const next = { ...f, [field]: value }
        // auto-preenche validade = emissão + 12m enquanto não for editada à mão
        if (field === 'data_emissao' && !validadeTouched) {
          next.validade = plus12Months(value)
        }
        return next
      })
      if (field === 'validade') setValidadeTouched(true)
    }
  }

  function onPickFile(e) {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    setPreview({ url: URL.createObjectURL(f), isPdf: f.type === 'application/pdf' })
  }

  const hasImage = Boolean(file) || Boolean(existingKey)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!hasImage) {
      setError('A imagem da receita é obrigatória.')
      return
    }
    setBusy(true)
    setError('')
    try {
      let imagem_key = existingKey
      if (file) {
        const { upload_url, key } = await uploads.presign(file.type)
        await uploadToStorage(upload_url, file)
        imagem_key = key
      }

      const payload = {
        data_emissao: form.data_emissao || null,
        validade: form.validade || null,
        medico_nome: form.medico_nome.trim() || null,
        medico_crm: form.medico_crm.trim() || null,
        od_esferico: num(form.od_esferico),
        od_cilindrico: num(form.od_cilindrico),
        od_eixo: int(form.od_eixo),
        od_adicao: num(form.od_adicao),
        oe_esferico: num(form.oe_esferico),
        oe_cilindrico: num(form.oe_cilindrico),
        oe_eixo: int(form.oe_eixo),
        oe_adicao: num(form.oe_adicao),
        dp: num(form.dp),
        dp_longe: num(form.dp_longe),
        dp_perto: num(form.dp_perto),
        observacoes: form.observacoes.trim() || null,
        imagem_key,
      }

      const saved = isEdit
        ? await receitas.update(id, payload)
        : await receitas.create(clienteId, payload)
      nav(`/receitas/${saved.id}`)
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
          <h1>{isEdit ? 'Editar receita' : 'Nova receita'}</h1>
          <p className="subtitle">Envie a imagem da receita — os demais dados são opcionais</p>
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <form onSubmit={handleSubmit}>
        <fieldset className="fieldset">
          <legend>
            Imagem da receita <span className="req">*</span>
          </legend>
          <div
            className={`dropzone ${preview ? 'has-preview' : ''}`}
            onClick={() => fileRef.current?.click()}
          >
            {preview ? (
              preview.isPdf ? (
                <span>📄 PDF selecionado — clique para trocar</span>
              ) : (
                <img src={preview.url} alt="pré-visualização da receita" />
              )
            ) : (
              <span>Clique para enviar (JPG, PNG, WebP ou PDF)</span>
            )}
          </div>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            onChange={onPickFile}
            style={{ display: 'none' }}
          />
          <span className="hint">Único campo obrigatório. A data de emissão assume hoje por padrão.</span>
        </fieldset>

        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => setShowDetails((v) => !v)}
          aria-expanded={showDetails}
        >
          {showDetails ? '− Ocultar detalhes da receita' : '+ Adicionar detalhes da receita'}
        </button>

        {showDetails && (
          <div style={{ marginTop: '1.1rem' }}>
            <fieldset className="fieldset">
              <legend>Emissão</legend>
              <div className="form-grid">
                <div className="field">
                  <label htmlFor="emissao">Data de emissão</label>
                  <input
                    id="emissao"
                    type="date"
                    value={form.data_emissao}
                    onChange={set('data_emissao')}
                  />
                  <span className="hint">Padrão: hoje.</span>
                </div>
                <div className="field">
                  <label htmlFor="validade">Validade</label>
                  <input
                    id="validade"
                    type="date"
                    value={form.validade}
                    onChange={set('validade')}
                  />
                  <span className="hint">Preenchida automaticamente (+12 meses), editável.</span>
                </div>
                <div className="field">
                  <label>Médico</label>
                  <input value={form.medico_nome} onChange={set('medico_nome')} />
                </div>
                <div className="field">
                  <label>CRM</label>
                  <input value={form.medico_crm} onChange={set('medico_crm')} />
                </div>
              </div>
            </fieldset>

            <fieldset className="fieldset">
              <legend>Graus</legend>
              <div className="form-grid">
                <OlhoFields prefix="od" label="Olho Direito (OD)" form={form} set={set} />
                <OlhoFields prefix="oe" label="Olho Esquerdo (OE)" form={form} set={set} />
              </div>
            </fieldset>

            <fieldset className="fieldset">
              <legend>Distância pupilar</legend>
              <div className="form-grid">
                <div className="field">
                  <label>DP (única)</label>
                  <input type="number" step="0.5" value={form.dp} onChange={set('dp')} />
                </div>
                <div className="field">
                  <label>DP longe</label>
                  <input type="number" step="0.5" value={form.dp_longe} onChange={set('dp_longe')} />
                </div>
                <div className="field">
                  <label>DP perto</label>
                  <input type="number" step="0.5" value={form.dp_perto} onChange={set('dp_perto')} />
                </div>
              </div>
            </fieldset>

            <fieldset className="fieldset">
              <legend>Observações</legend>
              <div className="field">
                <textarea
                  value={form.observacoes}
                  onChange={set('observacoes')}
                  style={{ minHeight: '120px' }}
                />
              </div>
            </fieldset>
          </div>
        )}

        <div className="form-actions">
          <Link to={backTo} className="btn btn-ghost">
            Cancelar
          </Link>
          <button className="btn btn-primary" disabled={busy || !hasImage}>
            {busy ? 'Salvando…' : 'Salvar receita'}
          </button>
        </div>
      </form>
    </>
  )
}
