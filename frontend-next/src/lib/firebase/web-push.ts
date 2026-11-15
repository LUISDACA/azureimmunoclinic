"use client";

import { apiClient } from "@/lib/api/client";
import type { MessagePayload, Messaging } from "firebase/messaging";

type EnableResult = "enabled" | "permission-required" | "denied" | "unsupported";
type WebPushConfigResponse = {
  firebaseConfig: {
    apiKey: string;
    authDomain: string;
    projectId: string;
    storageBucket: string;
    messagingSenderId: string;
    appId: string;
    measurementId?: string;
  };
  vapidKey: string;
};

let foregroundUnsubscribe: (() => void) | undefined;

async function getMessagingClient() {
  const [appSdk, messagingSdk] = await Promise.all([
    import("firebase/app"),
    import("firebase/messaging"),
  ]);
  if (!(await messagingSdk.isSupported())) return null;

  const response = await fetch("/api/firebase-web-config", {
    cache: "no-store",
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error("browser_push_configuration_unavailable");
  const config = (await response.json()) as WebPushConfigResponse;

  const appName = "immunoclinic-web-push";
  const app = appSdk.getApps().find((candidate) => candidate.name === appName)
    ?? appSdk.initializeApp(config.firebaseConfig, appName);
  const messaging = messagingSdk.getMessaging(app);
  const serviceWorkerRegistration = await navigator.serviceWorker.register(
    "/firebase-messaging-sw.js",
    { scope: "/", updateViaCache: "none" },
  );
  await navigator.serviceWorker.ready;

  return { messaging, messagingSdk, serviceWorkerRegistration, vapidKey: config.vapidKey };
}

function showForegroundNotification(payload: MessagePayload) {
  if (typeof window === "undefined" || Notification.permission !== "granted") return;
  const title = payload.notification?.title || "ImmunoClinic";
  const body = payload.notification?.body || "Tienes una actualización. Abre la aplicación para consultarla.";
  const notice = new Notification(title, {
    body,
    icon: "/brand/ucc_logo_app.png",
    tag: "immunoclinic-updates",
  });
  notice.onclick = () => {
    window.focus();
    window.location.assign(new URL("/", window.location.origin).toString());
    notice.close();
  };
}

function listenForForegroundMessages(
  messaging: Messaging,
  messagingSdk: typeof import("firebase/messaging"),
) {
  foregroundUnsubscribe?.();
  foregroundUnsubscribe = messagingSdk.onMessage(messaging, showForegroundNotification);
}

export async function registerBrowserPush(options: { requestPermission?: boolean } = {}): Promise<EnableResult> {
  if (typeof window === "undefined" || !("Notification" in window) || !("serviceWorker" in navigator)) {
    return "unsupported";
  }

  let permission = Notification.permission;
  if (permission === "default" && options.requestPermission) {
    permission = await Notification.requestPermission();
  }
  if (permission === "default") return "permission-required";
  if (permission !== "granted") return "denied";

  const client = await getMessagingClient();
  if (!client) return "unsupported";

  const token = await client.messagingSdk.getToken(client.messaging, {
    vapidKey: client.vapidKey,
    serviceWorkerRegistration: client.serviceWorkerRegistration,
  });
  if (!token) throw new Error("browser_push_token_unavailable");

  await apiClient.post("/notifications/device-token", { token, platform: "web" });
  listenForForegroundMessages(client.messaging, client.messagingSdk);
  return "enabled";
}

export function stopBrowserForegroundNotifications() {
  foregroundUnsubscribe?.();
  foregroundUnsubscribe = undefined;
}
