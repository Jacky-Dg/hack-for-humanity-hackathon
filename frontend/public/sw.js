const CACHE='clearpath-shell-v1';
self.addEventListener('install',event=>{self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(self.clients.claim());});
// No caching of map tiles, user locations, images, API responses, or reports.
self.addEventListener('fetch',event=>{});
