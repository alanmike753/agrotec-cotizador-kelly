"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { ApiError, request } from "@/lib/api";
import { AuthUser } from "@/lib/types";
import PwaRegister from "@/components/PwaRegister";

type AuthContextValue = {
  user: AuthUser;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth debe utilizarse dentro de AppShell.");
  return value;
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      setUser(await request<AuthUser>("/api/auth/me"));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setUser(null);
      else throw error;
    }
  }

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!user && pathname !== "/login") router.replace("/login");
    if (user?.role !== "admin" && (pathname.startsWith("/configuracion") || pathname.startsWith("/usuarios"))) {
      router.replace("/");
    }
  }, [loading, pathname, router, user]);

  async function logout() {
    await request("/api/auth/logout", { method: "POST" });
    setUser(null);
    router.replace("/login");
  }

  if (pathname === "/login") {
    return <AuthContext.Provider value={{ user: user as AuthUser, refresh, logout }}>{children}</AuthContext.Provider>;
  }
  if (loading || !user) return <main className="auth-loading">Verificando sesión segura…</main>;
  if (user.role !== "admin" && (pathname.startsWith("/configuracion") || pathname.startsWith("/usuarios"))) {
    return <main className="auth-loading">Redirigiendo al cotizador…</main>;
  }

  return <AuthContext.Provider value={{ user, refresh, logout }}>
    <PwaRegister />
    <header className="site-header"><div className="header-inner">
      <Link href="/" className="brand" aria-label="Ir al cotizador">
        <img src="/agrotec-logo.png" alt="Agrotec de Occidente" />
        <span><strong>Agrotec</strong><small>Cotizador privado Kelly</small></span>
      </Link>
      <nav>
        <Link href="/">Cotizador</Link>
        {user.role === "admin" && <Link href="/configuracion">Administración</Link>}
        {user.role === "admin" && <Link href="/usuarios">Usuarios</Link>}
        <button className="session-button" onClick={logout}>Salir</button>
      </nav>
      <div className="session-user"><strong>{user.full_name}</strong><span>{user.role === "admin" ? "Administrador" : "Vendedor"}</span></div>
    </div></header>
    {children}
    <footer>Uso interno · Sesión protegida · Agrotec de Occidente</footer>
  </AuthContext.Provider>;
}
