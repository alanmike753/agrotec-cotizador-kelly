function backendUrl() {
  const host = process.env.BACKEND_HOSTPORT || "127.0.0.1:8000";
  return host.startsWith("http://") || host.startsWith("https://") ? host : `http://${host}`;
}

export async function GET() {
  try {
    const response = await fetch(`${backendUrl()}/api/health`, { cache: "no-store", signal: AbortSignal.timeout(4000) });
    if (!response.ok) return Response.json({ status: "unhealthy" }, { status: 503 });
    return Response.json({ status: "ok" });
  } catch {
    return Response.json({ status: "unhealthy" }, { status: 503 });
  }
}
