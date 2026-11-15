"use client";

import { useEffect, useState } from "react";
import { BellRing, BellOff, LoaderCircle } from "lucide-react";
import { toast } from "sonner";
import { registerBrowserPush } from "@/lib/firebase/web-push";

type Status = "checking" | "default" | "granted" | "denied" | "unsupported" | "activating" | "error";

export function BrowserPushSetup() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (!("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) {
        setStatus("unsupported");
        return;
      }
      setStatus(Notification.permission);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  async function enable() {
    setStatus("activating");
    try {
      const result = await registerBrowserPush({ requestPermission: true });
      if (result === "enabled") {
        setStatus("granted");
        toast.success("Este navegador recibirá notificaciones de ImmunoClinic.");
      } else if (result === "denied") {
        setStatus("denied");
      } else if (result === "unsupported") {
        setStatus("unsupported");
      } else {
        setStatus("default");
      }
    } catch {
      setStatus("error");
      toast.error("No se pudo activar las notificaciones del navegador.");
    }
  }

  const granted = status === "granted";
  const disabled = status === "checking" || status === "activating" || status === "unsupported" || status === "denied";

  return (
    <section className="flex flex-col gap-3 rounded-xl border border-[color:var(--divider)] bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[color:var(--primary)]/10 text-[color:var(--interactive-foreground)]">
          {status === "denied" || status === "unsupported"
            ? <BellOff className="h-5 w-5" aria-hidden="true" />
            : <BellRing className="h-5 w-5" aria-hidden="true" />}
        </span>
        <div className="min-w-0">
          <h2 className="text-sm font-bold">Notificaciones en este navegador</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {granted
              ? "Este navegador tiene permiso para recibir avisos de ImmunoClinic."
              : status === "denied"
                ? "El permiso está bloqueado. Habilítalo en los ajustes del sitio de tu navegador."
                : status === "unsupported"
                  ? "Este navegador o dispositivo no admite notificaciones push para esta página."
                  : "Actívalas para recibir avisos aunque no tengas abierta esta página."}
          </p>
          {status === "error" && <p role="alert" className="mt-1 text-sm text-destructive">No se pudo registrar este navegador. Intenta de nuevo.</p>}
        </div>
      </div>
      <button
        type="button"
        onClick={enable}
        disabled={disabled}
        className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-xl bg-[color:var(--action)] px-4 py-2 text-sm font-bold text-[color:var(--action-foreground)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {status === "activating" || status === "checking"
          ? <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
          : <BellRing className="h-4 w-4" aria-hidden="true" />}
        {status === "activating" ? "Activando…" : granted ? "Sincronizar este navegador" : "Activar notificaciones"}
      </button>
    </section>
  );
}
