import { zodResolver } from '@hookform/resolvers/zod';
import { Building2, Plus, Search, UserPlus } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { PageHeader } from '@/components/layout/PageHeader';
import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { FormField, Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Select } from '@/components/ui/Select';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { TD, TH, THead, TR, TableWrap, TBody } from '@/components/ui/Table';
import { useDebounce } from '@/hooks/useDebounce';
import {
  useCreateDepartment,
  useCreateUser,
  useDeleteDepartment,
  useDepartmentsQuery,
  useUpdateUser,
  useUsersQuery,
} from '@/hooks/useAdmin';
import { formatDate, pluralize } from '@/lib/format';
import type { DepartmentDto } from '@/types/domain';

const userSchema = z.object({
  full_name: z.string().trim().min(2, 'Enter the full name').max(120),
  email: z.string().trim().email('Enter a valid email address'),
  password: z
    .string()
    .min(10, 'Use at least 10 characters')
    .regex(/[A-Z]/, 'Include an uppercase letter')
    .regex(/\d/, 'Include a digit'),
  role: z.enum(['admin', 'employee']),
  department_id: z.string(),
});

type UserValues = z.infer<typeof userSchema>;

export function UsersPage() {
  const users = useUsersQuery();
  const departments = useDepartmentsQuery();
  const updateUser = useUpdateUser();
  const createUser = useCreateUser();
  const createDepartment = useCreateDepartment();
  const deleteDepartment = useDeleteDepartment();

  const [search, setSearch] = useState('');
  const debounced = useDebounce(search, 250);
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [departmentName, setDepartmentName] = useState('');
  const [pendingDepartment, setPendingDepartment] = useState<DepartmentDto | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<UserValues>({
    resolver: zodResolver(userSchema),
    defaultValues: { full_name: '', email: '', password: '', role: 'employee', department_id: '' },
  });

  const filtered = useMemo(() => {
    const needle = debounced.trim().toLowerCase();
    const items = users.data ?? [];
    if (!needle) return items;
    return items.filter(
      (user) =>
        user.full_name.toLowerCase().includes(needle) ||
        user.email.toLowerCase().includes(needle) ||
        user.role.includes(needle),
    );
  }, [debounced, users.data]);

  const submitUser = handleSubmit(async (values) => {
    await createUser.mutateAsync({
      full_name: values.full_name.trim(),
      email: values.email.trim(),
      password: values.password,
      role: values.role,
      department_id: values.department_id ? Number(values.department_id) : null,
    });
    reset({ full_name: '', email: '', password: '', role: 'employee', department_id: '' });
    setUserModalOpen(false);
  });

  return (
    <div className="space-y-5">
      <PageHeader
        title="Users & departments"
        description="Roles decide who can administer the corpus; departments decide what employees can retrieve."
        actions={
          <Button icon={<UserPlus aria-hidden="true" className="h-4 w-4" />} onClick={() => setUserModalOpen(true)}>
            Add user
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Users</CardTitle>
              <div className="w-56">
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search users"
                  aria-label="Search users"
                  icon={<Search aria-hidden="true" className="h-4 w-4" />}
                />
              </div>
            </CardHeader>
            <CardBody className="p-0 pb-1">
              {users.isPending ? (
                <SkeletonTable rows={5} cols={4} />
              ) : users.error ? (
                <ErrorState message="Could not load users." onRetry={() => void users.refetch()} />
              ) : !filtered.length ? (
                <EmptyState
                  icon={<UserPlus aria-hidden="true" className="h-5 w-5" />}
                  title="No users found"
                  hint="Add a colleague or clear the search."
                />
              ) : (
                <TableWrap className="border-t border-slate-100">
                  <THead>
                    <TH>User</TH>
                    <TH>Role</TH>
                    <TH>Department</TH>
                    <TH>Status</TH>
                    <TH className="hidden 2xl:table-cell">Joined</TH>
                  </THead>
                  <TBody>
                    {filtered.map((user) => (
                      <TR key={user.id}>
                        <TD>
                          <div className="flex items-center gap-3">
                            <Avatar name={user.full_name} size="sm" />
                            <div className="min-w-0">
                              <p className="truncate font-medium text-slate-800">{user.full_name}</p>
                              <p className="truncate text-xs text-slate-500">{user.email}</p>
                            </div>
                          </div>
                        </TD>
                        <TD>
                          <Select
                            aria-label={`Role for ${user.full_name}`}
                            value={user.role}
                            disabled={updateUser.isPending}
                            className="h-8 w-28 text-xs"
                            onChange={(event) =>
                              updateUser.mutate({ id: user.id, role: event.target.value as 'admin' | 'employee' })
                            }
                          >
                            <option value="employee">employee</option>
                            <option value="admin">admin</option>
                          </Select>
                        </TD>
                        <TD>
                          <Select
                            aria-label={`Department for ${user.full_name}`}
                            value={user.department_id ?? ''}
                            disabled={updateUser.isPending}
                            className="h-8 w-36 text-xs"
                            onChange={(event) =>
                              updateUser.mutate({
                                id: user.id,
                                ...(event.target.value
                                  ? { department_id: Number(event.target.value) }
                                  : { clear_department: true }),
                              })
                            }
                          >
                            <option value="">No department</option>
                            {(departments.data ?? []).map((department) => (
                              <option key={department.id} value={department.id}>
                                {department.name}
                              </option>
                            ))}
                          </Select>
                        </TD>
                        <TD>
                          <Button
                            variant={user.is_active ? 'ghost' : 'secondary'}
                            size="sm"
                            disabled={updateUser.isPending}
                            onClick={() => updateUser.mutate({ id: user.id, is_active: !user.is_active })}
                          >
                            {user.is_active ? 'Deactivate' : 'Activate'}
                          </Button>
                        </TD>
                        <TD className="hidden whitespace-nowrap text-xs text-slate-500 2xl:table-cell">
                          {formatDate(user.created_at)}
                        </TD>
                      </TR>
                    ))}
                  </TBody>
                </TableWrap>
              )}
            </CardBody>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <div>
              <CardTitle className="text-base">Departments</CardTitle>
              <p className="mt-0.5 text-sm text-slate-500">
                {departments.data?.length ?? 0} {pluralize(departments.data?.length ?? 0, 'department')}
              </p>
            </div>
          </CardHeader>
          <CardBody className="space-y-3 pt-2">
            <form
              className="flex items-end gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                if (!departmentName.trim()) return;
                createDepartment.mutate(
                  { name: departmentName.trim() },
                  { onSuccess: () => setDepartmentName('') },
                );
              }}
            >
              <FormField label="New department" htmlFor="dept-name">
                <Input
                  id="dept-name"
                  value={departmentName}
                  onChange={(event) => setDepartmentName(event.target.value)}
                  placeholder="Finance"
                />
              </FormField>
              <Button type="submit" loading={createDepartment.isPending} icon={<Plus aria-hidden="true" className="h-4 w-4" />}>
                Add
              </Button>
            </form>

            {departments.isPending ? (
              <p className="text-sm text-slate-500">Loading…</p>
            ) : departments.error ? (
              <ErrorState compact message="Could not load departments." onRetry={() => void departments.refetch()} />
            ) : !departments.data?.length ? (
              <EmptyState
                icon={<Building2 aria-hidden="true" className="h-5 w-5" />}
                title="No departments"
                hint="Create one to scope document visibility."
              />
            ) : (
              <ul className="divide-y divide-slate-100">
                {departments.data.map((department) => (
                  <li key={department.id} className="flex items-center justify-between gap-2 py-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-800">{department.name}</p>
                      {department.description ? (
                        <p className="truncate text-xs text-slate-500">{department.description}</p>
                      ) : null}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-rose-600 hover:bg-rose-50"
                      onClick={() => setPendingDepartment(department)}
                    >
                      Delete
                    </Button>
                  </li>
                ))}
              </ul>
            )}

            <p className="text-xs text-slate-500">
              A department cannot be deleted while users or documents still reference it.
            </p>
          </CardBody>
        </Card>
      </div>

      <Modal
        open={userModalOpen}
        onClose={() => setUserModalOpen(false)}
        title="Add a user"
        description="Admins can administer the corpus; employees can chat and read documents they are allowed to see."
        dismissible={!createUser.isPending}
        footer={
          <>
            <Button variant="secondary" onClick={() => setUserModalOpen(false)} disabled={createUser.isPending}>
              Cancel
            </Button>
            <Button type="submit" form="add-user-form" loading={createUser.isPending}>
              Create user
            </Button>
          </>
        }
      >
        <form id="add-user-form" noValidate className="space-y-4" onSubmit={(event) => void submitUser(event)}>
          <FormField label="Full name" error={errors.full_name?.message} required htmlFor="user-name">
            <Input id="user-name" invalid={Boolean(errors.full_name)} {...register('full_name')} />
          </FormField>
          <FormField label="Email" error={errors.email?.message} required htmlFor="user-email">
            <Input id="user-email" type="email" invalid={Boolean(errors.email)} {...register('email')} />
          </FormField>
          <FormField
            label="Temporary password"
            error={errors.password?.message}
            hint="At least 10 characters, one uppercase letter and one digit."
            required
            htmlFor="user-password"
          >
            <Input id="user-password" type="text" invalid={Boolean(errors.password)} {...register('password')} />
          </FormField>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Role" htmlFor="user-role">
              <Select id="user-role" {...register('role')}>
                <option value="employee">employee</option>
                <option value="admin">admin</option>
              </Select>
            </FormField>
            <FormField label="Department" htmlFor="user-department">
              <Select id="user-department" {...register('department_id')}>
                <option value="">No department</option>
                {(departments.data ?? []).map((department) => (
                  <option key={department.id} value={department.id}>
                    {department.name}
                  </option>
                ))}
              </Select>
            </FormField>
          </div>
          <p className="text-xs text-slate-500">
            <Badge color="amber" size="sm">
              note
            </Badge>{' '}
            Departments affect retrieval: employees only see documents shared with their department.
          </p>
        </form>
      </Modal>

      <ConfirmDialog
        open={pendingDepartment !== null}
        title="Delete department"
        message={`Delete "${pendingDepartment?.name ?? ''}"? This fails if users or documents still reference it.`}
        confirmLabel="Delete"
        loading={deleteDepartment.isPending}
        onClose={() => setPendingDepartment(null)}
        onConfirm={() => {
          if (pendingDepartment) deleteDepartment.mutate(pendingDepartment.id);
          setPendingDepartment(null);
        }}
      />
    </div>
  );
}
