// StrideBoard service worker: keeps the site's files on the phone and shows an
// offline page. Served at /sw.js by app.py, which fills in __ASSET_VERSION__ so this
// always matches the files the pages load. Nothing to edit here when files change.
const VERSION = "strideboard-__ASSET_VERSION__";
const SHELL = [
  "/offline",
  "/static/css/style.css?v=__ASSET_VERSION__",
  "/static/js/app.js?v=__ASSET_VERSION__",
  "/static/fonts/outfit.woff2?v=__ASSET_VERSION__",
  "/static/manifest.json",
  "/static/icons/icon-192.png",
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
    // Static files: from the phone if saved, otherwise download once and save a copy.
    event.respondWith(
      caches.open(VERSION).then((cache) =>
        cache.match(req).then((hit) => hit || fetch(req).then((resp) => {
          if (resp.ok) cache.put(req, resp.clone());
          return resp;
        })))
    );
  }
});
