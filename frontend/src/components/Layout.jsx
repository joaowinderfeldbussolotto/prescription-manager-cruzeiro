import { NavLink, Link, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import Logo from './Logo'

export default function Layout() {
  const { user, logout } = useAuth()
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand">
            <Logo size={28} />
            <span className="wordmark">aureye</span>
          </Link>
          <nav className="nav">
            <NavLink to="/" end>
              Dashboard
            </NavLink>
            <NavLink to="/clientes">Clientes</NavLink>
          </nav>
          <span className="topbar-spacer" />
          {user && (
            <div className="user-chip">
              <span>{user.nome || user.email}</span>
              <span className="badge badge-role">{user.role}</span>
              <button className="btn btn-ghost btn-sm" onClick={logout}>
                Sair
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
