"use client";

import { FormEvent, useEffect, useState } from "react";
import { request } from "@/lib/api";
import { AuthUser } from "@/lib/types";

export default function UsersPage() {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "seller">("seller");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const data = await request<{ items: AuthUser[] }>("/api/users");
    setUsers(data.items);
  }
  useEffect(() => { load().catch(err => setError(err.message)); }, []);

  async function create(event: FormEvent) {
    event.preventDefault(); setError("");
    try {
      await request<AuthUser>("/api/users", {
        method: "POST", body: JSON.stringify({ full_name: fullName, email, password, role }),
      });
      setFullName(""); setEmail(""); setPassword(""); setRole("seller");
      setMessage("Usuario creado correctamente."); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "No se pudo crear el usuario."); }
  }

  async function update(user: AuthUser, changes: object) {
    setError("");
    try {
      await request<AuthUser>(`/api/users/${user.id}`, { method: "PATCH", body: JSON.stringify(changes) });
      setMessage("Usuario actualizado."); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "No se pudo actualizar el usuario."); }
  }

  async function resetPassword(user: AuthUser) {
    const password = window.prompt(`Nueva contraseña temporal para ${user.full_name} (mínimo 12 caracteres):`);
    if (!password) return;
    await update(user, { password });
  }

  return <main className="page-shell users-page">
    <section className="hero compact"><div><p className="eyebrow">Seguridad</p><h1>Usuarios y permisos</h1><p>Crea cuentas individuales. No compartas contraseñas entre vendedores.</p></div></section>
    {message && <div className="alert success" role="status">{message}</div>}
    {error && <div className="alert error" role="alert">{error}</div>}
    <div className="users-grid">
      <section className="settings-card user-create"><h2>Nuevo usuario</h2>
        <form onSubmit={create}>
          <label><span>Nombre</span><input value={fullName} onChange={event => setFullName(event.target.value)} required minLength={2} /></label>
          <label><span>Correo</span><input type="email" value={email} onChange={event => setEmail(event.target.value)} required /></label>
          <label><span>Contraseña inicial</span><input type="password" value={password} onChange={event => setPassword(event.target.value)} required minLength={12} autoComplete="new-password" /></label>
          <label><span>Rol</span><select value={role} onChange={event => setRole(event.target.value as typeof role)}><option value="seller">Vendedor</option><option value="admin">Administrador</option></select></label>
          <button>Crear usuario</button>
        </form>
      </section>
      <section className="admin-card"><div className="admin-heading"><div><h2>Cuentas activas</h2><p>Los cambios de contraseña o rol cierran las sesiones existentes del usuario.</p></div><strong>{users.length} usuarios</strong></div>
        <div className="users-list">{users.map(user => <article key={user.id}>
          <div><strong>{user.full_name}</strong><span>{user.email}</span><small>Último acceso: {user.last_login_at ? new Date(user.last_login_at).toLocaleString("es-MX") : "Aún no ingresa"}</small></div>
          <label><span>Rol</span><select value={user.role} onChange={event => update(user, { role: event.target.value })}><option value="seller">Vendedor</option><option value="admin">Administrador</option></select></label>
          <div className="user-actions"><button className="secondary" onClick={() => resetPassword(user)}>Cambiar contraseña</button><button className={user.is_active ? "danger-button" : "secondary"} onClick={() => update(user, { is_active: !user.is_active })}>{user.is_active ? "Desactivar" : "Reactivar"}</button></div>
        </article>)}</div>
      </section>
    </div>
  </main>;
}
