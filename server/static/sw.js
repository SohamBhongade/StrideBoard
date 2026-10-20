// StrideBoard service worker: caches the app shell and shows an offline page.
// Served at /sw.js (see app.py) so it covers the whole site.
// Change VERSION (and ASSET_VERSION in app.py) whenever style.css or app.js change,
// so phones get the new files.
const VERSION = "strideboard-v8";
const SHELL = [
  "/offline",
  "/static/css/style.css?v=4",
  "/static/js/app.js?v=4",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/apple-touch-icon.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Delete caches from older versions
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  // Only handle our own GET requests; never touch the step API or form posts.
  if (req.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;

  if (req.mode === "navigate") {
    // Pages: always try the network (data must be fresh), offline page if it fails.
    event.respondWith(fetch(req).catch(() => caches.match("/offline")));
    return;
  }
  if (url.pathname.startsWith("/static/")) {
    // Static files: cache first, then network.
    event.respondWith(caches.match(req).then((hit) => hit || fetch(req)));
  }
});
