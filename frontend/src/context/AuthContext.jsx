import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { auth } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const hydrate = useCallback(async () => {
    try {
      const me = await auth.me()
      setUser(me)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    hydrate()
  }, [hydrate])

  const loginGoogle = useCallback(async (idToken) => {
    const me = await auth.loginGoogle(idToken)
    setUser(me)
    return me
  }, [])

  const loginDev = useCallback(async (email) => {
    const me = await auth.loginDev(email)
    setUser(me)
    return me
  }, [])

  const logout = useCallback(async () => {
    try {
      await auth.logout()
    } finally {
      setUser(null)
    }
  }, [])

  const value = { user, loading, loginGoogle, loginDev, logout, refresh: hydrate }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve ser usado dentro de <AuthProvider>')
  return ctx
}
