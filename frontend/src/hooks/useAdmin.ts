import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, apiErrorMessage } from '@/lib/api';
import { queryKeys } from '@/lib/constants';
import { toast } from '@/store/uiStore';
import type { Paginated, Role, User } from '@/types/api';
import type { AdminStatsDto, AuditFilters, AuditLogDto, DepartmentDto } from '@/types/domain';

export function useAdminStatsQuery() {
  return useQuery({
    queryKey: queryKeys.adminStats,
    queryFn: async () => {
      const { data } = await api.get<AdminStatsDto>('/admin/stats');
      return data;
    },
    staleTime: 30_000,
  });
}

/** `GET /users` returns a plain array (not paginated). */
export function useUsersQuery() {
  return useQuery({
    queryKey: ['users'] as const,
    queryFn: async () => {
      const { data } = await api.get<User[]>('/users');
      return data;
    },
    staleTime: 30_000,
  });
}

export function useDepartmentsQuery() {
  return useQuery({
    queryKey: queryKeys.departments,
    queryFn: async () => {
      const { data } = await api.get<DepartmentDto[]>('/departments');
      return data;
    },
    staleTime: 5 * 60_000,
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      email: string;
      full_name: string;
      password: string;
      role: Role;
      department_id: number | null;
    }) => {
      const { data } = await api.post<User>('/users', input);
      return data;
    },
    onSuccess: (user) => {
      void queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('User created', user.email);
    },
    onError: (error) => toast.error('Could not create the user', apiErrorMessage(error)),
  });
}

/** `PATCH /users/{id}` — role, department, name and active flag. */
export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      id: number;
      role?: Role;
      department_id?: number | null;
      is_active?: boolean;
      full_name?: string;
      clear_department?: boolean;
    }) => {
      const { id, ...payload } = input;
      const { data } = await api.patch<User>(`/users/${id}`, payload);
      return data;
    },
    onSuccess: (user) => {
      void queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('User updated', user.full_name);
    },
    onError: (error) => toast.error('Update failed', apiErrorMessage(error)),
  });
}

export function useCreateDepartment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { name: string; description?: string | null }) => {
      const { data } = await api.post<DepartmentDto>('/departments', input);
      return data;
    },
    onSuccess: (department) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.departments });
      toast.success('Department created', department.name);
    },
    onError: (error) => toast.error('Could not create the department', apiErrorMessage(error)),
  });
}

export function useDeleteDepartment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/departments/${id}`);
      return id;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.departments });
      toast.success('Department deleted');
    },
    onError: (error) => toast.error('Could not delete the department', apiErrorMessage(error)),
  });
}

export function useAuditLogsQuery(filters: AuditFilters) {
  return useQuery({
    queryKey: queryKeys.auditLogs({ ...filters }),
    queryFn: async () => {
      const { data } = await api.get<Paginated<AuditLogDto>>('/admin/audit-logs', {
        params: {
          page: filters.page ?? 1,
          page_size: filters.page_size ?? 20,
          ...(filters.user_id ? { user_id: filters.user_id } : {}),
          ...(filters.action ? { action: filters.action } : {}),
          ...(filters.from ? { from: filters.from } : {}),
          ...(filters.to ? { to: filters.to } : {}),
        },
      });
      return data;
    },
    staleTime: 15_000,
    placeholderData: keepPreviousData,
  });
}
