import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import Students from '@/app/admin/students/page';
import CreateStudent from '@/app/admin/students/create/page';
import Detail from '@/app/admin/students/[id]/page';
import Admins from '@/app/admin/admins/page';
import { createAdmin, createStudent, updateStudentProfile } from '@/lib/api/admin';
import { useAuthStore } from '@/lib/auth/store';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), useSearchParams: () => new URLSearchParams('tab=info'), usePathname: () => '/admin/students' }));
vi.mock('@/lib/api/admin', () => ({
  listStudents: vi.fn(async () => ({ page: 1, page_size: 20, total: 0, total_pages: 0, has_next: false, has_previous: false, items: [] })),
  assignCertificateSigner: vi.fn(),
  listAdmins: vi.fn(async () => []),
  listCertificateSignerAssignments: vi.fn(async () => []),
  getAcademicOptions: vi.fn(async () => ({ programs: ['Medicina', 'Enfermería'], campuses: ['Bogotá', 'Cali'], semesters: Array.from({ length: 10 }, (_, i) => i + 1) })),
  getStudent: vi.fn(async () => ({ id: 'synthetic', email: 'synthetic@example.invalid', role: 'student', is_active: true, profile: null, created_at: '2026-10-09T12:00:00Z' })),
  listStudentCertificates: vi.fn(async () => []),
  createStudent: vi.fn(), createAdmin: vi.fn(), updateStudentProfile: vi.fn(), deactivateStudent: vi.fn(), reactivateStudent: vi.fn(), deleteStudent: vi.fn(),
}));
vi.mock('@/lib/api/users', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/users')>();
  return {
    ...actual,
    getMe: vi.fn(async () => ({
      id: 'synthetic-admin', email: 'admin@example.invalid', role: 'admin', is_active: true,
      profile: { id: 'synthetic-profile', first_name: 'Synthetic', last_name: 'Admin', sex: 'female', program: 'Medicina', campus: 'Pasto' },
    })),
  };
});
beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); useAuthStore.setState({ role: 'admin', userId: 'synthetic-admin', isAuthenticated: true }); });
afterEach(cleanup);
function mount(children: React.ReactNode) { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>); }
async function checkLabels(labels: string[]) {
  const user = userEvent.setup();
  for (const text of labels) {
    const label = screen.getByText(text, { selector: 'label' }) as HTMLLabelElement;
    const control = document.getElementById(label.htmlFor);
    expect(control).not.toBeNull();
    await user.click(label); expect(control).toHaveFocus();
  }
  const ids = Array.from(document.querySelectorAll('input,select')).map(e => e.id);
  expect(ids.every(Boolean)).toBe(true); expect(new Set(ids).size).toBe(ids.length);
  expect(createStudent).not.toHaveBeenCalled(); expect(createAdmin).not.toHaveBeenCalled(); expect(updateStudentProfile).not.toHaveBeenCalled();
}

it('list filter labels focus their native controls without changing URL/filter values', async () => {
  mount(<Students />);
  await checkLabels(['Buscar', 'Estado', 'Esquema', 'Semestre', 'Sexo']);
  expect(screen.getByLabelText('Estado')).toHaveValue('');
});

it('create labels include required, date, sex and import fields with unique IDs', async () => {
  mount(<CreateStudent />);
  await checkLabels(['Correo *', 'Documento *', 'Nombres *', 'Apellidos *', 'Sexo *', 'Fecha de nacimiento', 'Programa asignado', 'Campus asignado', 'Archivo Excel o CSV']);
  expect(screen.getByLabelText('Sexo *')).toHaveValue('female');
  expect(screen.getByLabelText('Fecha de nacimiento')).toHaveAttribute('type', 'date');
});

it('administrator creation labels focus fields and does not expose an initial password input', async () => {
  mount(<Admins />); const user = userEvent.setup(); await user.click(await screen.findByRole('button', { name: 'Crear admin' }));
  await checkLabels(['Correo *', 'Nombres', 'Apellidos', 'Cargo', 'Programa *', 'Campus *']);
  expect(screen.queryByLabelText('Contraseña *')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Programa *')).toBeRequired();
});

it('detail edit labels focus controls without losing context or sending any mutation', async () => {
  const params = Promise.resolve({ id: 'synthetic' });
  await act(async () => { mount(<Detail params={params} />); });
  const user = userEvent.setup(); await user.click(await screen.findByRole('button', { name: 'Editar datos' }));
  await checkLabels(['Nombre', 'Apellido', 'Documento', 'Codigo institucional', 'Fecha nacimiento', 'Sexo', 'Telefono', 'EPS', 'Semestre', 'Contacto emergencia', 'Tel. emergencia']);
  const semester = screen.getByRole('combobox', { name: 'Semestre' });
  expect(semester.querySelectorAll('option')).toHaveLength(11);
});
