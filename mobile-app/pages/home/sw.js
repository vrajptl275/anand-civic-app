const CACHE_NAME = 'civic-plus-cache-v1';

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll([
                './index.html',
                '../../public/css/style.css',
                '../../public/js/main.js',
                '../../public/assets/img/hero.png'
            ]);
        })
    );
});

self.addEventListener('fetch', (event) => {
    // Network-First strategy ensures the Python Backend is strictly favored,
    // intercepting cleanly to offline cached UI only upon terminal failure.
    
    // Ignore API proxies because we can't mathematically cache dynamic Python interactions natively
    if (event.request.url.includes('/api/')) {
        return event.respondWith(fetch(event.request));
    }

    event.respondWith(
        fetch(event.request).catch(() => {
            return caches.match(event.request);
        })
    );
});
