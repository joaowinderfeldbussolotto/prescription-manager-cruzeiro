// Formatação pt-BR de datas e graus ópticos.

export function formatDate(value) {
  if (!value) return '—'
  // value pode ser 'YYYY-MM-DD' (date) — evita shift de fuso tratando como local
  const [y, m, d] = String(value).slice(0, 10).split('-')
  if (!y || !m || !d) return value
  return `${d}/${m}/${y}`
}

export function formatDateTime(value) {
  if (!value) return '—'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return '—'
  return dt.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

// Esférico/cilíndrico/adição: sempre com sinal e 2 casas (ex -2.50, +1.00)
export function formatGrau(value) {
  if (value === null || value === undefined || value === '') return '—'
  const n = Number(value)
  if (Number.isNaN(n)) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}`
}

export function formatEixo(value) {
  if (value === null || value === undefined || value === '') return '—'
  return `${value}°`
}

export function formatDp(value) {
  if (value === null || value === undefined || value === '') return '—'
  return `${Number(value).toFixed(1)} mm`
}
