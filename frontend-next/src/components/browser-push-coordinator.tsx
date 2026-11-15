"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/lib/auth/store";
import { registerBrowserPush, stopBrowserForegroundNotifications } from "@/lib/firebase/web-push";

export function BrowserPushCoordinator() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const userId = useAuthStore((state) => state.userId);

  useEffect(() => {
    if (!isAuthenticated || !userId || typeof Notification === "undefined" || Notification.permission !== "granted") {
      stopBrowserForegroundNotifications();
      return;
    }

    let active = true;
    void registerBrowserPush().then(() => {
      if (!active) stopBrowserForegroundNotifications();
    }).catch(() => {
      // Push registration is optional; keep app login and in-app notifications usable.
    });

    return () => {
      active = false;
      stopBrowserForegroundNotifications();
    };
  }, [isAuthenticated, userId]);

  return null;
}
