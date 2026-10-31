// src/HOCS/withPermissions.tsx
import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export type PermissionMode = 'all' | 'any';

export const PERMISSION_MAP: Record<string, { permissions: string[]; mode: PermissionMode }> = {
  dashboard: { permissions: [], mode: 'any' },
  keys: { permissions: ['keys.view', 'keys.create'], mode: 'any' },
  rules: { permissions: ['inventory_rules.view', 'inventory_rules.create'], mode: 'any' },
  shifts: { permissions: ['shifts.view', 'shifts.create'], mode: 'any' },
  scans: { permissions: ['scans.view.any', 'scans.view.own', 'scans.create'], mode: 'any' },
  admin: { permissions: ['admin.access', 'admin.users.view', 'admin.users.promote'], mode: 'any' },
  security: { permissions: [], mode: 'any' },
};

export const checkPermission = (
  userPermissions: Record<string, boolean> = {},
  requiredPermissions: string[] = [],
  mode: PermissionMode = 'any',
  userRole?: string,
  userRoleFromAPI?: string
): { allowed: boolean; missing?: string[]; required?: string[] } => {
  const isAdmin = userRole?.toLowerCase() === 'admin' || userRoleFromAPI?.toLowerCase() === 'admin';
  if (isAdmin) return { allowed: true };

  if (!requiredPermissions || requiredPermissions.length === 0) return { allowed: true };

  if (!userPermissions || Object.keys(userPermissions).length === 0) {
    return { allowed: false, required: requiredPermissions, missing: requiredPermissions };
  }

  if (mode === 'all') {
    const missing = requiredPermissions.filter((p) => !userPermissions[p]);
    if (missing.length > 0) {
      return { allowed: false, missing, required: requiredPermissions };
    }
    return { allowed: true };
  }

  if (mode === 'any') {
    const hasAny = requiredPermissions.some((p) => userPermissions[p] === true);
    if (!hasAny) {
      return { allowed: false, required: requiredPermissions };
    }
    return { allowed: true };
  }

  return { allowed: false };
};

export function withPermission<P extends object>(
  Component: React.ComponentType<P>,
  pageKey: string,
  fallbackPath: string = '/dashboard'
) {
  const WrappedComponent = (props: P) => {
    const user = useAuthStore((state) => state.user);
    const permissions = user?.permissions || {};
    const requirement = PERMISSION_MAP[pageKey];

    const { allowed, missing, required } = checkPermission(
      permissions,
      requirement?.permissions || [],
      requirement?.mode || 'any',
      user?.role,
      user?.user_role
    );

    if (!allowed) {
      if (missing && missing.length > 0) {
        console.warn(`🔒 [withPermission] Missing permissions for ${pageKey}: ${missing.join(', ')}`);
      } else if (required && required.length > 0) {
        console.warn(`🔒 [withPermission] Need at least one of: ${required.join(', ')}`);
      }
      return <Navigate to={fallbackPath} replace />;
    }

    return <Component {...props} />;
  };

  WrappedComponent.displayName = `withPermission(${Component.displayName || Component.name || 'Component'})`;
  return WrappedComponent;
}

export function usePermission(pageKey: string) {
  const user = useAuthStore((state) => state.user);
  const permissions = user?.permissions || {};
  const requirement = PERMISSION_MAP[pageKey];

  if (!requirement) {
    return { allowed: true, missing: [], required: [] };
  }

  return checkPermission(
    permissions,
    requirement.permissions,
    requirement.mode,
    user?.role,
    user?.user_role
  );
}

export function useHasPermission(permission: string): boolean {
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.role?.toLowerCase() === 'admin' || user?.user_role?.toLowerCase() === 'admin';
  if (isAdmin) return true;
  return Boolean(user?.permissions?.[permission]);
}

export function PermissionGuard({
  children,
  pageKey,
  fallback = null,
}: {
  children: React.ReactNode;
  pageKey: string;
  fallback?: React.ReactNode;
}) {
  const { allowed } = usePermission(pageKey);
  if (!allowed) return <>{fallback}</>;
  return <>{children}</>;
}
