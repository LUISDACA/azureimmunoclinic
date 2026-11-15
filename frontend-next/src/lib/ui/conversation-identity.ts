import type { ConversationUser } from "@/lib/api/types";

export function conversationRoleLabel(user: ConversationUser): string {
  if (user.role === "student") return "Estudiante";
  if (user.role === "app_admin") return "Administrador de aplicación";
  if (user.role === "admin") return user.job_title?.trim() || "Administrador";
  return "Usuario";
}

export function conversationIdentity(user: ConversationUser): string {
  const name = user.name?.trim();
  return name
    ? `${name} · ${conversationRoleLabel(user)}`
    : `${conversationRoleLabel(user)} · ${user.email || "Usuario"}`;
}
