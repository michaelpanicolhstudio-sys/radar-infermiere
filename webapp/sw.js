/* Service worker: tiene una copia dell'app e degli ultimi dati, così funziona anche senza rete.
   Strategia: prima la rete (dati freschi), se manca si usa l'ultima copia salvata. */
const CACHE = "radar-__VERSIONE__";
const BASE = ["./", "index.html", "style.css", "app.js", "dati.json", "manifest.webmanifest",
              "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(BASE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((nomi) => Promise.all(nomi.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== self.location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then((risposta) => {
        if (risposta.ok && risposta.type === "basic") {
          const copia = risposta.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copia));
        }
        return risposta;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true })
        .then((r) => r || (e.request.mode === "navigate" ? caches.match("index.html") : Response.error())))
  );
});
