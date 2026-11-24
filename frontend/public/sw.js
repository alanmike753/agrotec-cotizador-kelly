self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));
// Deliberadamente no se cachean respuestas: el cotizador es privado y los datos
// comerciales siempre deben obtenerse autenticados y actualizados desde el servidor.
