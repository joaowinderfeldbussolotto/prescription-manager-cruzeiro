import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import ClientesList from './pages/ClientesList'
import ClienteForm from './pages/ClienteForm'
import ClienteDetail from './pages/ClienteDetail'
import ReceitaForm from './pages/ReceitaForm'
import ReceitaView from './pages/ReceitaView'
import Agente from './pages/Agente'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/clientes" element={<ClientesList />} />
          <Route path="/clientes/novo" element={<ClienteForm />} />
          <Route path="/clientes/:id" element={<ClienteDetail />} />
          <Route path="/clientes/:id/editar" element={<ClienteForm />} />
          <Route path="/clientes/:clienteId/receitas/nova" element={<ReceitaForm />} />
          <Route path="/receitas/:id" element={<ReceitaView />} />
          <Route path="/receitas/:id/editar" element={<ReceitaForm />} />
          <Route path="/agente" element={<Agente />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
