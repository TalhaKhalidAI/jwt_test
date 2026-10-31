// src/pages/Admin/query.tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { http } from '../../api/http/https';
import { ToastMsgs } from '../../api/toastUtils';
import type {
  AdminUser,
  PermissionListResponse,
  UpdateUserPayload,
  PasswordConfirmPayload,
  UpdatePasswordPayload,
  SetPermissionsPayload,
  BulkPermissionsPayload,
  RemovePermissionsPayload,
  TempTokenResponse,
} from './types';

export const useAdminUsersQuery = () => {
  return useQuery({
    queryKey: ['admin', 'users'],
    queryFn: async (): Promise<AdminUser[]> => {
      // 1. Fetch user permissions mapping with info
      const permData = await http.get<{
        users: Record<string, { email: string; name: string; role: string; permissions: Record<string, boolean> }>;
        pagination: { total: number };
      }>('/admin/admin_access/users/permissions?include_user_info=true&limit=200');

      // 2. Fetch full user config accounts to capture statuses
      let usersList: any[] = [];
      try {
        const fullUsers = await http.get<{ users: any[] }>('/users/users_config/users?limit=200');
        usersList = fullUsers?.users || [];
      } catch (err) {
        console.warn('Could not load extended user statuses, using permissions listing', err);
      }

      const usersById: Record<number, any> = {};
      usersList.forEach((u) => {
        usersById[u.id] = u;
      });

      const list: AdminUser[] = Object.entries(permData.users || {}).map(([idStr, u]) => {
        const numId = Number(idStr);
        const full = usersById[numId] || {};
        return {
          id: numId,
          email: u.email || full.email || '',
          name: u.name || full.name || '',
          role: u.role || full.user_role || full.role || 'user',
          user_role: full.user_role || u.role,
          disabled: Boolean(full.disabled),
          is_deleted: Boolean(full.is_deleted),
          permissions: u.permissions || full.permissions || {},
          mfa_enabled: full.mfa_enabled,
          mfa_method: full.mfa_method,
        };
      });

      return list;
    },
    staleTime: 1000 * 30,
  });
};

export const useAllPermissionsQuery = () => {
  return useQuery({
    queryKey: ['admin', 'all_permissions'],
    queryFn: async () => {
      const res = await http.get<PermissionListResponse>('/admin/admin_access/get_all_permissions');
      return res.permissions || [];
    },
    staleTime: 1000 * 60 * 5,
  });
};

export const useUpdateUserMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, payload }: { userId: number; payload: UpdateUserPayload }) => {
      return await http.put<AdminUser>(`/admin/admin_access/account/${userId}`, payload);
    },
    onSuccess: (_, vars) => {
      ToastMsgs.success(`Account for User #${vars.userId} updated`);
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (err: any) => {
      ToastMsgs.error(err?.response?.data?.detail || err?.message || 'Failed to update account');
    },
  });
};

export const useDisableAccountMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, payload }: { userId: number; payload?: PasswordConfirmPayload }) => {
      return await http.post(`/admin/admin_access/account/disable/${userId}`, payload || {});
    },
    onSuccess: (_, vars) => {
      ToastMsgs.success(`User #${vars.userId} account disabled`);
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (err: any) => {
      ToastMsgs.error(err?.response?.data?.detail || err?.message || 'Failed to disable account');
    },
  });
};

export const useEnableAccountMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, payload }: { userId: number; payload?: PasswordConfirmPayload }) => {
      return await http.post(`/admin/admin_access/account/enable/${userId}`, payload || {});
    },
    onSuccess: (_, vars) => {
      ToastMsgs.success(`User #${vars.userId} account enabled`);
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (err: any) => {
      ToastMsgs.error(err?.response?.data?.detail || err?.message || 'Failed to enable account');
    },
  });
};

export const useDeleteAccountMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, payload }: { userId: number; payload?: PasswordConfirmPayload }) => {
      return await http.delete(`/admin/admin_access/account/${userId}`, { data: payload || {} });
    },
    onSuccess: (_, vars) => {
      ToastMsgs.success(`User #${vars.userId} soft-deleted`);
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (err: any) => {
      ToastMsgs.error(err?.response?.data?.detail || err?.message || 'Failed to delete account');
    },
  });
};

export const useRestoreAccountMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, otp }: { userId: number; otp?: string }) => {
      const url = otp
        ? `/admin/admin_access/account/restore/${userId}?otp=${encodeURIComponent(otp)}`
        : `/admin/admin_access/account/restore/${userId}`;
      return await http.post(url);
    },
    onSuccess: (_, vars) => {
      ToastMsgs.success(`User #${vars.userId} account restored`);
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (err: any) => {
      ToastMsgs.error(err?.response?.data?.detail || err?.message || 'Failed to restore account');
    },
  });
};

export const useUpdatePasswordMutation = () => {
  return useMutation({
    mutationFn: async ({ userId, payload }: { userId: number; payload: UpdatePasswordPayload }) => {
      return await http.put(`/admin/admin_access/account/password/${userId}`, payload);
    },
    onSuccess: (_, vars) => {
      ToastMsgs.success(`Password updated successfully for User #${vars.userId}`);
    },
    onError: (err: any) => {
      ToastMsgs.error(err?.response?.data?.detail || err?.message || 'Failed to update password');
    },
  });
};

export const useTempTokenMutation = () => {
  return useMutation({
    mutationFn: async ({
      userId,
      restorePasswd,
      otp,
    }: {
      userId: number;
      restorePasswd?: boolean;
      otp?: string;
    }) => {
      const params = new URLSearchParams();
      if (restorePasswd) params.append('restore_passwd', 'true');
      if (otp) params.append('otp', otp);
      const query = params.toString() ? `?${params.toString()}` : '';
      return await http.post<TempTokenResponse>(`/admin/admin_access/account/temp_token/${userId}${query}`);
    },
    onSuccess: (_, vars) => {
      ToastMsgs.success(`Temporary token issued for User #${vars.userId}`);
    },
    onError: (err: any) => {
      ToastMsgs.error(err?.response?.data?.detail || err?.message || 'Failed to generate temporary token');
    },
  });
};

export const useResetAutoKillMutation = () => {
  return useMutation({
    mutationFn: async (otp?: string) => {
      const url = otp
        ? `/admin/admin_access/reset-auto-kill?otp=${encodeURIComponent(otp)}`
        : '/admin/admin_access/reset-auto-kill';
      return await http.post(url);
    },
    onSuccess: () => {
      ToastMsgs.success('Safety Mode / Auto-Kill Switch has been reset successfully');
    },
    onError: (err: any) => {
      ToastMsgs.error(err?.response?.data?.detail || err?.message || 'Failed to reset Auto-Kill');
    },
  });
};

export const useSetPermissionsMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: SetPermissionsPayload) => {
      return await http.post('/admin/admin_access/set_permissions', payload);
    },
    onSuccess: (_, vars) => {
      ToastMsgs.success(`Permissions updated for User #${vars.user_id}`);
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (err: any) => {
      ToastMsgs.error(err?.response?.data?.detail || err?.message || 'Failed to set permissions');
    },
  });
};

export const useBulkSetPermissionsMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: BulkPermissionsPayload) => {
      return await http.post('/admin/admin_access/set_permissions_bulk', payload);
    },
    onSuccess: () => {
      ToastMsgs.success('Bulk permissions assigned successfully');
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (err: any) => {
      ToastMsgs.error(err?.response?.data?.detail || err?.message || 'Failed to apply bulk permissions');
    },
  });
};

export const useRemovePermissionsMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: RemovePermissionsPayload) => {
      return await http.delete('/admin/admin_access/remove_permissions', { data: payload });
    },
    onSuccess: (_, vars) => {
      ToastMsgs.success(`Permissions removed for User #${vars.user_id}`);
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (err: any) => {
      ToastMsgs.error(err?.response?.data?.detail || err?.message || 'Failed to remove permissions');
    },
  });
};
