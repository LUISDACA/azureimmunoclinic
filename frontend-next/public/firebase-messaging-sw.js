/* Firebase web configuration is public and served at runtime by Next.js. */
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.stopImmediatePropagation();
  const target = new URL("/", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (new URL(client.url).origin === self.location.origin) {
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});

importScripts("/api/firebase-web-config?format=worker");
importScripts("https://www.gstatic.com/firebasejs/11.10.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/11.10.0/firebase-messaging-compat.js");

firebase.initializeApp(self.__IMMUNO_FIREBASE_CONFIG__);
firebase.messaging();
