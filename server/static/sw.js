// StrideBoard service worker: keeps the site's files on the phone, keeps a copy of your Home
// page to show when there's no internet, and shows an offline page for everything else. Served at /sw.js by app.py, which fills in __ASSET_VERSION__ so this
// always matches the files the pages load. Nothing to edit here when files change.
const VERSION = "strideboard-__ASSET_VERSION__";
const HOME_COPY = "/__home-copy";   // the last Home page that loaded, for offline use
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

function forgetHome() {
  return caches.open(VERSION).then((cache) => cache.delete(HOME_COPY));
}

// Home: fresh from the network when possible (and a copy kept); the copy when offline,
// marked so the page can say it's offline and grey out buttons that need the internet.
function home(req) {
  return fetch(req).then((resp) => {
    const loggedIn = resp.ok && !resp.redirected && new URL(resp.url).pathname === "/";
    if (loggedIn) {
      const saved = Date.now();
      resp.clone().text().then((html) => caches.open(VERSION).then((cache) =>
        cache.put(HOME_COPY, new Response(html.replace("<html ", `<html data-offline-copy="${saved}" `),
          { headers: { "Content-Type": "text/html; charset=utf-8" } }))));
    } else {
      forgetHome();   // logged out or session over: don't keep anyone's Home around
    }
    return resp;
  }).catch(() => caches.match(HOME_COPY).then((copy) => copy || caches.match("/offline")));
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  // Logging out (link or form) forgets the saved Home, so the next person can't see it.
  if (url.origin === location.origin && url.pathname === "/logout") event.waitUntil(forgetHome());
  // Only handle our own GET requests; never touch the step API or form posts.
  if (req.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  // Downloads (the iPhone Shortcut file) go straight to Safari: if they pass through here,
  // Safari shows the file as text instead of offering to add it.
  if (url.pathname === "/iphone-shortcut") return;

  if (req.mode === "navigate" && url.pathname === "/" && !url.search) {
    event.respondWith(home(req));
    return;
  }
  if (req.mode === "navigate") {
    // Other pages: always try the network (data must be fresh), offline page if it fails.
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
