import { statusValidade } from '../utils/receita'

export default function ValidadeBadge({ validade }) {
  const { label, tone } = statusValidade(validade)
  return <span className={`badge ${tone}`}>{label}</span>
}
