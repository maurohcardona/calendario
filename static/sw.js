// ══════════════════════════════════════════════════════════════
// SERVICE WORKER: Laboratorio Hospital Balestrini
// Estrategia: Cache First (velocidad) con Background Sync
// ══════════════════════════════════════════════════════════════

// Versión del cache (se reemplaza automáticamente con update_sw_version.py)
const CACHE_VERSION = '20260430-141250';
const CACHE_NAME = `lab-balestrini-${CACHE_VERSION}`;
const OFFLINE_URL = '/offline/';

// Recursos críticos a cachear en instalación
const CRITICAL_CACHE = [
  '/turnos/calendario/',
  '/static/css/apple-design.css',
  '/static/vendor/bootstrap/bootstrap.min.css',
  '/static/vendor/bootstrap/bootstrap.bundle.min.js',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/static/manifest.json',
  OFFLINE_URL,
];

// ══════════════════════════════════════════════════════════════
// INSTALACIÓN
// ══════════════════════════════════════════════════════════════
self.addEventListener('install', event => {
  console.log(`[SW] Instalando Service Worker ${CACHE_NAME}`);

  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[SW] Cacheando recursos críticos');
        return cache.addAll(CRITICAL_CACHE);
      })
      .then(() => {
        console.log('[SW] Instalación completa - activando inmediatamente');
        return self.skipWaiting();
      })
      .catch(err => {
        console.error('[SW] Error en instalación:', err);
      })
  );
});

// ══════════════════════════════════════════════════════════════
// ACTIVACIÓN
// ══════════════════════════════════════════════════════════════
self.addEventListener('activate', event => {
  console.log(`[SW] Activando Service Worker ${CACHE_NAME}`);

  event.waitUntil(
    // Limpiar caches viejos (solo los de esta app)
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME && cacheName.startsWith('lab-balestrini-')) {
            console.log('[SW] Eliminando cache viejo:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
    .then(() => {
      console.log('[SW] Cache limpiado - tomando control de clientes');
      return self.clients.claim();
    })
  );
});

// ══════════════════════════════════════════════════════════════
// FETCH: ESTRATEGIA CACHE FIRST
// ══════════════════════════════════════════════════════════════
self.addEventListener('fetch', event => {
  const { request } = event;

  // Solo cachear GET requests
  if (request.method !== 'GET') return;

  // Ignorar requests a URLs externas
  if (!request.url.startsWith(self.location.origin)) return;

  // NO cachear admin, autenticación ni APIs
  if (
    request.url.includes('/admin/') ||
    request.url.includes('/accounts/') ||
    request.url.includes('/api/')
  ) {
    return; // Ir directo a red
  }

  event.respondWith(
    caches.match(request)
      .then(cachedResponse => {
        if (cachedResponse) {
          // ✅ CACHE HIT: Respuesta instantánea desde cache
          console.log('[SW] 🚀 Cache hit:', request.url);

          // Background sync: actualizar cache en segundo plano
          fetch(request)
            .then(networkResponse => {
              if (networkResponse && networkResponse.status === 200) {
                caches.open(CACHE_NAME).then(cache => {
                  cache.put(request, networkResponse.clone());
                  console.log('[SW] 🔄 Cache actualizado:', request.url);
                });
              }
            })
            .catch(() => {}); // Ignorar errores de red en background

          return cachedResponse;
        }

        // ❌ CACHE MISS: Ir a la red y guardar respuesta
        console.log('[SW] 📡 Fetching from network:', request.url);

        return fetch(request)
          .then(networkResponse => {
            if (networkResponse && networkResponse.status === 200) {
              const responseToCache = networkResponse.clone();
              caches.open(CACHE_NAME).then(cache => {
                cache.put(request, responseToCache);
                console.log('[SW] 💾 Guardado en cache:', request.url);
              });
            }
            return networkResponse;
          })
          .catch(() => {
            // 🔌 OFFLINE: Página offline para navegación
            if (request.mode === 'navigate') {
              return caches.match(OFFLINE_URL);
            }

            // Para otros recursos: respuesta de error
            return new Response('Offline', {
              status: 503,
              statusText: 'Service Unavailable',
              headers: new Headers({ 'Content-Type': 'text/plain' }),
            });
          });
      })
  );
});

// ══════════════════════════════════════════════════════════════
// MENSAJES: Control desde la página principal
// ══════════════════════════════════════════════════════════════
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    console.log('[SW] Recibido SKIP_WAITING - actualizando');
    self.skipWaiting();
  }
});

console.log(`[SW] Cargado: ${CACHE_NAME} | Estrategia: Cache First + Background Sync`);
