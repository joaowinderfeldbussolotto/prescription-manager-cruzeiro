import axios from 'axios'

// baseURL relativa: em dev o Vite faz proxy /api -> backend; em prod o nginx.
// withCredentials envia/recebe o cookie de sessão httpOnly.
const http = axios.create({
  baseURL: '/api',
  withCredentials: true,
})

// Extrai a mensagem de erro amigável vinda do backend (campo `detail`).
export function errorMessage(err, fallback = 'Algo deu errado. Tente novamente.') {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    // erros de validação do FastAPI
    return detail.map((d) => d.msg).join('; ')
  }
  return fallback
}

export const auth = {
  loginGoogle: (idToken) => http.post('/auth/google', { id_token: idToken }).then((r) => r.data),
  loginDev: (email) => http.post('/auth/dev-login', { email }).then((r) => r.data),
  me: () => http.get('/auth/me').then((r) => r.data),
  logout: () => http.post('/auth/logout').then((r) => r.data),
}

export const clientes = {
  list: (params) => http.get('/clientes', { params }).then((r) => r.data),
  get: (id) => http.get(`/clientes/${id}`).then((r) => r.data),
  create: (data) => http.post('/clientes', data).then((r) => r.data),
  update: (id, data) => http.put(`/clientes/${id}`, data).then((r) => r.data),
  remove: (id) => http.delete(`/clientes/${id}`).then((r) => r.data),
}

export const receitas = {
  listByCliente: (clienteId) =>
    http.get(`/clientes/${clienteId}/receitas`).then((r) => r.data),
  get: (id) => http.get(`/receitas/${id}`).then((r) => r.data),
  create: (clienteId, data) =>
    http.post(`/clientes/${clienteId}/receitas`, data).then((r) => r.data),
  update: (id, data) => http.put(`/receitas/${id}`, data).then((r) => r.data),
  remove: (id) => http.delete(`/receitas/${id}`).then((r) => r.data),
  extrairDados: (imagemKey) =>
    http.post('/receitas/extracao-ia', { imagem_key: imagemKey }).then((r) => r.data),
}

export const uploads = {
  presign: (contentType) =>
    http.post('/uploads/presigned-url', { content_type: contentType }).then((r) => r.data),
}

export const dashboard = {
  get: () => http.get('/dashboard').then((r) => r.data),
}

// PUT direto no storage (MinIO/S3) usando a presigned URL. Não passa pelo
// axios `http` (baseURL /api) — vai direto pro endpoint do storage.
export async function uploadToStorage(uploadUrl, file) {
  await axios.put(uploadUrl, file, {
    headers: { 'Content-Type': file.type },
    withCredentials: false,
  })
}

export default http
