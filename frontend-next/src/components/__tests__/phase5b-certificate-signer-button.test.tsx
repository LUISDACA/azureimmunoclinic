import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import Admins from "@/app/admin/admins/page";
import {
  assignCertificateSigner,
  createAdmin,
  deleteAdmin,
  getAcademicOptions,
  listAdmins,
  listCertificateSignerAssignments,
} from "@/lib/api/admin";
import type { User } from "@/lib/api/types";
import { useAuthStore } from "@/lib/auth/store";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/api/admin", () => ({
  assignCertificateSigner: vi.fn(),
  createAdmin: vi.fn(),
  deleteAdmin: vi.fn(),
  getAcademicOptions: vi.fn(),
  listAdmins: vi.fn(),
  listCertificateSignerAssignments: vi.fn(),
}));
vi.mock("@/lib/api/communications", () => ({ createThread: vi.fn() }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), warning: vi.fn(), error: vi.fn() } }));

const admins = [
  {
    id: "synthetic-admin-a",
    email: "admin-a@example.invalid",
    role: "admin",
    is_active: true,
    profile: { first_name: "Synthetic", last_name: "A", program: "Medicina", campus: "Pasto" },
  },
  {
    id: "synthetic-admin-b",
    email: "admin-b@example.invalid",
    role: "admin",
    is_active: true,
    profile: { first_name: "Synthetic", last_name: "B", program: "Medicina", campus: "Pasto" },
  },
] as User[];

let assignments: Awaited<ReturnType<typeof listCertificateSignerAssignments>>;
const clients: QueryClient[] = [];

function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } },
  });
  clients.push(client);
  render(<QueryClientProvider client={client}><Admins /></QueryClientProvider>);
  return client;
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.spyOn(window, "confirm").mockReturnValue(true);
  useAuthStore.setState({ userId: "synthetic-app-admin", role: "app_admin", isAuthenticated: true });
  assignments = [];
  vi.mocked(listAdmins).mockResolvedValue(admins);
  vi.mocked(listCertificateSignerAssignments).mockImplementation(async () => assignments);
  vi.mocked(getAcademicOptions).mockResolvedValue({ programs: ["Medicina"], campuses: ["Pasto"], semesters: [] });
  vi.mocked(createAdmin).mockResolvedValue(admins[0] as never);
  vi.mocked(deleteAdmin).mockResolvedValue(undefined);
  vi.mocked(assignCertificateSigner).mockImplementation(async (payload) => {
    assignments = assignments
      .map((row) => row.program === payload.program && row.campus === payload.campus
        ? { ...row, active: false }
        : row)
      .concat({
        ...payload,
        id: "synthetic-assignment",
        assigned_by_id: "synthetic-app-admin",
        active: true,
        created_at: "2026-11-21T12:00:00Z",
      });
    return assignments.at(-1)!;
  });
});

afterEach(() => {
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
  vi.restoreAllMocks();
});

it("lets the application admin designate one scoped admin and marks the choice", async () => {
  mount();
  const row = await screen.findByText(admins[1].email).then((email) => email.closest("tr")!);
  const button = within(row).getByRole("button", { name: "Hacer responsable" });

  await userEvent.click(button);

  await waitFor(() => expect(vi.mocked(assignCertificateSigner).mock.calls[0]?.[0]).toEqual({
    program: "Medicina",
    campus: "Pasto",
    admin_id: admins[1].id,
  }));
  expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("Synthetic B como responsable"));
  expect(await within(row).findByText("Responsable")).toBeInTheDocument();
});

it("asks before replacing the responsible admin and leaves the current choice on cancellation", async () => {
  assignments = [{
    id: "current-assignment",
    program: "Medicina",
    campus: "Pasto",
    admin_id: admins[0].id,
    assigned_by_id: "synthetic-app-admin",
    active: true,
    created_at: "2026-11-21T12:00:00Z",
  }];
  vi.mocked(window.confirm).mockReturnValue(false);
  mount();
  const row = await screen.findByText(admins[1].email).then((email) => email.closest("tr")!);

  await userEvent.click(within(row).getByRole("button", { name: "Hacer responsable" }));

  expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("Reemplazar al responsable actual"));
  expect(assignCertificateSigner).not.toHaveBeenCalled();
  expect(await screen.findByText("Responsable")).toBeInTheDocument();
});
