// 홈 화면 앱 설치용 최소 서비스 워커: 같은 사이트 요청만 그대로 네트워크로 보냅니다 (저장·캐시 안 함)
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  if (new URL(e.request.url).origin !== self.location.origin) return;
  e.respondWith(fetch(e.request));
});
