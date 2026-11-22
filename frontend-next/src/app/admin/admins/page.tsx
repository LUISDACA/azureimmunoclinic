"use client";
import { useSafeMutation as useMutation } from "@/lib/query/safe-mutation";
import { QueryError } from "@/components/query-error";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { toast } from "sonner";
import {
  CreateAdminRequest,
  assignCertificateSigner,
  createAdmin,
  deleteAdmin,
  getAcademicOptions,
  listAdmins,
  listCertificateSignerAssignments,
} from "@/lib/api/admin";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Modal } from "@/components/ui/modal";
import { createThread } from "@/lib/api/communications";
import { useRouter } from "next/navigation";
import { Select } from "@/components/ui/select";

const EMPTY: CreateAdminRequest = {
  email: "",
  program: "",
  campus: "",
};

export default function AdminManagementPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["admins"],
    queryFn: listAdmins,
  });
  const signerAssignments = useQuery({
    queryKey: ["certificate-signer-assignments"],
    queryFn: listCertificateSignerAssignments,
  });

  const [showForm, setShowForm] = useState(false);
  const academicOptions = useQuery({
    queryKey: ["academic-options"],
    queryFn: getAcademicOptions,
    enabled: showForm,
  });
  const [form, setForm] = useState<CreateAdminRequest>(EMPTY);
  const [messageTarget, setMessageTarget] = useState<{ id: string; name: string } | null>(null);
  const [messageSubject, setMessageSubject] = useState("");
  const [messageBody, setMessageBody] = useState("");
  const [messageError, setMessageError] = useState<string | null>(null);
  const [confirmedWrite, setConfirmedWrite] = useState<{ message: string; readVersion: number } | null>(null);
  const [writeError, setWriteError] = useState<string | null>(null);
  const confirmedMessage = confirmedWrite?.readVersion === queryClient.getQueryState(["admins"])?.dataUpdateCount
    ? confirmedWrite?.message : null;
  const retry = () => refetch({ cancelRefetch: false });

  function beginWrite() {
    setConfirmedWrite(null);
    setWriteError(null);
  }
  function notifyWrite(success: string, confirmedButUnread: string, severity: "success" | "warning" = "success") {
    const read = queryClient.getQueryState(["admins"]);
    if (read?.status === "error") {
      setConfirmedWrite({ message: confirmedButUnread, readVersion: read.dataUpdateCount });
      toast.warning(confirmedButUnread);
    } else {
      setConfirmedWrite(null);
      if (severity === "warning") toast.warning(success);
      else toast.success(success);
    }
  }

  const create = useMutation({
    affectedQueries: [["admins"],["audit"]],
    mutationFn: (payload: CreateAdminRequest) => createAdmin(payload),
    onMutate: beginWrite,
    onSuccess: (account) => {
      const accepted = account.email_delivery_status === "accepted";
      const delivery = accepted
        ? "El proveedor aceptó el correo; la llegada a la bandeja no está confirmada."
        : "No se confirmó el envío del correo. No vuelvas a crear la cuenta; solicita ayuda para habilitar el acceso.";
      notifyWrite(
        `Administrador creado. ${delivery}`,
        `El administrador se creó, pero no se pudo actualizar la lista. ${delivery}`,
        accepted ? "success" : "warning",
      );
      setForm(EMPTY);
      setShowForm(false);
    },
    onError: () => { setWriteError("No se pudo crear el administrador."); toast.error("No se pudo crear"); },
  });

  const remove = useMutation({
    affectedQueries: [["admins"],["audit"]],
    mutationFn: (id: string) => deleteAdmin(id),
    onMutate: beginWrite,
    onSuccess: () => {
      notifyWrite("Administrador eliminado", "El administrador se eliminó, pero no se pudo actualizar la lista.");
    },
    onError: () => { setWriteError("No se pudo eliminar el administrador."); toast.error("No se pudo eliminar"); },
  });
  const assignSigner = useMutation({
    affectedQueries: [["admins"], ["certificate-signer-assignments"], ["audit"]],
    mutationFn: assignCertificateSigner,
    onMutate: beginWrite,
    onSuccess: (_assignment, payload) => {
      notifyWrite(
        `${payload.program} · ${payload.campus}: responsable de certificados actualizado.`,
        "La asignación se guardó, pero no se pudo actualizar la lista. Pulsa Actualizar lista.",
      );
    },
    onError: () => {
      setWriteError("No se pudo asignar al responsable de certificados.");
      toast.error("No se pudo asignar el responsable");
    },
  });
  const sendMessage = useMutation({
    affectedQueries: [["threads"], ["notifications"]],
    mutationFn: createThread,
    onError: () => setMessageError("No se pudo enviar el mensaje."),
    onSuccess: (thread) => {
      setMessageTarget(null);
      router.push(`/admin/communications/${encodeURIComponent(thread.id)}?returnTo=${encodeURIComponent("/admin/admins")}`);
    },
  });
  const busy = isFetching || signerAssignments.isFetching || create.isPending || remove.isPending || assignSigner.isPending || sendMessage.isPending;
  const readable = !error && !isLoading && data !== undefined;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight">Administradores</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Cuentas con permisos de administración por programa y sede. Designa aquí quién firma los certificados de cada ámbito.
          </p>
        </div>
        {readable && (
          <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:justify-end">
            <Button variant="outline" disabled={busy} onClick={retry}>Actualizar lista</Button>
            <Button disabled={busy} onClick={() => { setWriteError(null); setShowForm((s) => !s); }}>
              {showForm ? "Cancelar" : "Crear admin"}
            </Button>
          </div>
        )}
      </div>

      {error && confirmedMessage && <p role="status">{confirmedMessage}</p>}
      {writeError && <p role="status">{writeError}</p>}
      {signerAssignments.error && (
        <QueryError
          error={signerAssignments.error}
          retry={() => signerAssignments.refetch({ cancelRefetch: false })}
          retrying={signerAssignments.isFetching}
        />
      )}
      {showForm && readable && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Nuevo administrador</CardTitle>
          </CardHeader>
          <CardContent>
            {academicOptions.isLoading ? <p role="status">Cargando opciones académicas…</p> : academicOptions.error ? (
              <QueryError error={academicOptions.error} retry={() => academicOptions.refetch({ cancelRefetch: false })} retrying={academicOptions.isFetching} />
            ) : academicOptions.data && <form
              aria-label="Nuevo administrador"
              onSubmit={(event) => {
                event.preventDefault();
                if (busy || !readable || !event.currentTarget.reportValidity()) return;
                const payload: CreateAdminRequest = {
                  email: form.email.trim(),
                  program: form.program.trim(),
                  campus: form.campus.trim(),
                };
                for (const key of ["first_name", "last_name", "job_title"] as const) {
                  const value = form[key]?.trim();
                  if (value) payload[key] = value;
                }
                create.mutate(payload);
              }}
            >
              <fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2">
                <Field
                  label="Correo"
                  type="email"
                  required
                  value={form.email}
                  onChange={(v) => setForm({ ...form, email: v })}
                />
                <Field
                  label="Nombres"
                  maxLength={100}
                  value={form.first_name ?? ""}
                  onChange={(v) => setForm({ ...form, first_name: v })}
                />
                <Field
                  label="Apellidos"
                  maxLength={100}
                  value={form.last_name ?? ""}
                  onChange={(v) => setForm({ ...form, last_name: v })}
                />
                <Field
                  label="Cargo"
                  maxLength={150}
                  value={form.job_title ?? ""}
                  onChange={(v) => setForm({ ...form, job_title: v })}
                />
                <SelectField
                  label="Programa"
                  required
                  options={academicOptions.data.programs}
                  value={form.program}
                  onChange={(v) => setForm({ ...form, program: v })}
                />
                <SelectField
                  label="Campus"
                  required
                  options={academicOptions.data.campuses}
                  value={form.campus}
                  onChange={(v) => setForm({ ...form, campus: v })}
                />
                <p className="text-sm text-muted-foreground sm:col-span-2">
                  Se generará una contraseña temporal y se intentará enviar a este correo. El administrador deberá cambiarla al iniciar sesión.
                </p>
                <div className="sm:col-span-2">
                  <Button type="submit" disabled={busy}>
                    {create.isPending ? "Creando…" : "Crear"}
                  </Button>
                </div>
              </fieldset>
            </form>}
          </CardContent>
        </Card>
      )}

      {error ? (
        <QueryError error={error} retry={retry} retrying={isFetching} />
      ) : isLoading ? (
        <p role="status" className="text-sm text-muted-foreground">Cargando…</p>
      ) : data?.length === 0 ? (
        <p className="text-sm text-muted-foreground">No hay administradores creados</p>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/30 text-left">
                  <tr>
                    <th className="px-3 py-2">Nombre</th>
                    <th className="px-3 py-2">Email</th>
                    <th className="px-3 py-2">Programa</th>
                    <th className="px-3 py-2">Sede</th>
                    <th className="px-3 py-2">Estado</th>
                    <th className="px-3 py-2 text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.map((a) => {
                    const name = a.profile
                      ? `${a.profile.first_name} ${a.profile.last_name}`.trim()
                      : "—";
                    return (
                      <tr key={a.id} className="border-b last:border-0">
                        <td className="px-3 py-2 font-medium">{name}</td>
                        <td className="px-3 py-2 text-muted-foreground">
                          {a.email}
                        </td>
                        <td className="px-3 py-2">{a.profile?.program ?? "—"}</td>
                        <td className="px-3 py-2">{a.profile?.campus ?? "—"}</td>
                        <td className="px-3 py-2">
                          <Badge variant={a.is_active ? "success" : "muted"}>
                            {a.is_active ? "Activo" : "Inactivo"}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 text-right">
                          {signerAssignments.data?.some((assignment) =>
                            assignment.active && assignment.program === a.profile?.program &&
                            assignment.campus === a.profile?.campus && assignment.admin_id === a.id
                          ) ? (
                            <Badge variant="success" className="mr-1">Responsable</Badge>
                          ) : (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={busy || !signerAssignments.data || !a.is_active || !a.profile?.program || !a.profile?.campus}
                              onClick={() => {
                                if (!a.profile?.program || !a.profile.campus || !signerAssignments.data) return;
                                const current = signerAssignments.data.find((assignment) =>
                                  assignment.active && assignment.program === a.profile?.program &&
                                  assignment.campus === a.profile?.campus
                                );
                                const name = a.profile
                                  ? `${a.profile.first_name} ${a.profile.last_name}`.trim()
                                  : a.email;
                                const replacing = current && current.admin_id !== a.id;
                                const prompt = replacing
                                  ? `¿Reemplazar al responsable actual de ${a.profile.program} · ${a.profile.campus} y designar a ${name}?`
                                  : `¿Designar a ${name} como responsable de certificados para ${a.profile.program} · ${a.profile.campus}?`;
                                if (!confirm(prompt)) return;
                                assignSigner.mutate({
                                  program: a.profile.program,
                                  campus: a.profile.campus,
                                  admin_id: a.id,
                                });
                              }}
                            >
                              Hacer responsable
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={busy}
                            onClick={() => {
                              setMessageSubject("");
                              setMessageBody("");
                              setMessageError(null);
                              setMessageTarget({ id: a.id, name: name === "—" ? a.email : name });
                            }}
                          >
                            Enviar mensaje
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={busy}
                            onClick={() => {
                              if (confirm("¿Eliminar administrador?")) {
                                remove.mutate(a.id);
                              }
                            }}
                          >
                            Eliminar
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {messageTarget && (
        <Modal
          titleId="admin-message-title"
          descriptionId="admin-message-description"
          busy={sendMessage.isPending}
          onClose={() => setMessageTarget(null)}
        >
          <form
            aria-label="Enviar mensaje a administrador"
            onSubmit={(event) => {
              event.preventDefault();
              const subject = messageSubject.trim();
              const message = messageBody.trim();
              if (sendMessage.isPending || !messageTarget || subject.length < 3 || !message) {
                setMessageError("Escribe un asunto y un mensaje.");
                return;
              }
              setMessageError(null);
              sendMessage.mutate({
                subject,
                message,
                category: "admin",
                admin_id: messageTarget.id,
              });
            }}
            className="grid gap-4"
          >
            <div>
              <h2 id="admin-message-title" className="text-lg font-semibold">Mensaje a {messageTarget.name}</h2>
              <p id="admin-message-description" className="mt-1 text-sm text-muted-foreground">Se abrirá una conversación con este administrador.</p>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="admin-message-subject">Asunto</Label>
              <Input id="admin-message-subject" value={messageSubject} maxLength={200} disabled={sendMessage.isPending} onChange={(event) => setMessageSubject(event.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="admin-message-body">Mensaje</Label>
              <Textarea id="admin-message-body" value={messageBody} maxLength={4000} disabled={sendMessage.isPending} onChange={(event) => setMessageBody(event.target.value)} />
            </div>
            {messageError && <p role="alert" className="text-sm text-destructive">{messageError}</p>}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" disabled={sendMessage.isPending} onClick={() => setMessageTarget(null)}>Cancelar</Button>
              <Button type="submit" disabled={sendMessage.isPending}>{sendMessage.isPending ? "Enviando…" : "Enviar"}</Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
  required,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
  required?: boolean;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}{required && " *"}</Label>
      <Select id={id} value={value} required={required} onChange={(event) => onChange(event.target.value)}>
        <option value="">Selecciona una opción</option>
        {options.map((option) => <option key={option} value={option}>{option}</option>)}
      </Select>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  required,
  minLength,
  maxLength,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
  minLength?: number;
  maxLength?: number;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>
        {label}
        {required && " *"}
      </Label>
      <Input
        id={id}
        value={value}
        type={type}
        required={required}
        minLength={minLength}
        maxLength={maxLength}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
