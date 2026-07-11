// Status de validade da receita — dirige o badge "vencida / vencendo / válida".

function parseDateLocal(value) {
  const [y, m, d] = String(value).slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d)
}

function today() {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

/**
 * @returns {{ status: 'vencida'|'vencendo'|'valida', label: string, tone: string, dias: number }}
 */
export function statusValidade(validade, janelaDias = 30) {
  const v = parseDateLocal(validade)
  const t = today()
  const dias = Math.round((v - t) / 86400000)

  if (dias < 0) {
    return { status: 'vencida', label: 'Vencida', tone: 'badge-danger', dias }
  }
  if (dias <= janelaDias) {
    return {
      status: 'vencendo',
      label: dias === 0 ? 'Vence hoje' : `Vence em ${dias}d`,
      tone: 'badge-warn',
      dias,
    }
  }
  return { status: 'valida', label: 'Válida', tone: 'badge-ok', dias }
}
