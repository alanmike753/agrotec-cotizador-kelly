"use client";

import { FormEvent, useState } from "react";
import { request } from "@/lib/api";
import { AuthUser } from "@/lib/types";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError("");
    try {
      await request<AuthUser>("/api/auth/login", {
        method: "POST", body: JSON.stringify({ email, password }),
      });
      window.location.assign("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión.");
      setLoading(false);
    }
  }

  return <main className="login-page">
    <section className="login-card">
      <img src="/agrotec-logo.png" alt="Agrotec de Occidente" />
      <p className="eyebrow">Acceso privado</p>
      <h1>Cotizador Kelly</h1>
      <p>Inicia sesión con la cuenta proporcionada por el administrador.</p>
      {error && <div className="alert error" role="alert">{error}</div>}
      <form onSubmit={submit}>
        <label><span>Correo electrónico</span><input type="email" autoComplete="username" value={email} onChange={event => setEmail(event.target.value)} required /></label>
        <label><span>Contraseña</span><input type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required /></label>
        <button disabled={loading}>{loading ? "Verificando…" : "Iniciar sesión"}</button>
      </form>
      <small>La sesión utiliza una cookie segura; la contraseña nunca se almacena en el navegador.</small>
    </section>
  </main>;
}
