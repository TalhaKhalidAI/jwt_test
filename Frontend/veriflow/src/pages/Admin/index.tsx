// src/pages/Admin/index.tsx
import React, { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Tabs,
  Tab,
  CircularProgress,
  FormControlLabel,
  Checkbox,
  Grid,
  Paper,
  Alert,
} from '@mui/material';
import {
  ShieldOutlined as ShieldAlert,
  VpnKeyRounded as KeyRound,
  CheckCircleOutlineRounded as UserCheck,
  BlockRounded as UserX,
  LockRounded as Lock,
  RotateLeftRounded as RotateCcw,
  DeleteRounded as Trash2,
  EditRounded as Edit,
  AccessTimeRounded as Clock,
  ContentCopyRounded as Copy,
  CheckRounded as Check,
  RefreshRounded as RefreshCw,
  GroupRounded as Users,
  AdminPanelSettingsRounded as Settings,
} from "@mui/icons-material";
import {
  useAdminUsersQuery,
  useAllPermissionsQuery,
  useUpdateUserMutation,
  useDisableAccountMutation,
  useEnableAccountMutation,
  useDeleteAccountMutation,
  useRestoreAccountMutation,
  useUpdatePasswordMutation,
  useTempTokenMutation,
  useResetAutoKillMutation,
  useSetPermissionsMutation,
  useRemovePermissionsMutation,
  useBulkSetPermissionsMutation,
} from './query';
import type { AdminUser } from './types';
import { useAuthStore } from '../../store/authStore';
import { useMFAStatusQuery } from '../Security/query';
import { OtpBoxesInput } from '../../components/OtpModal';
import { CloseRounded as CloseIcon } from '@mui/icons-material';

export const AdminPage: React.FC = () => {
  const user = useAuthStore((state) => state.user);
  const { data: mfaStatus } = useMFAStatusQuery();
  const isMFAEnabled = Boolean(user?.mfa_enabled || mfaStatus?.mfa_enabled);

  const { data: users = [], isLoading: usersLoading, refetch: refetchUsers } = useAdminUsersQuery();
  const { data: allPermissions = [] } = useAllPermissionsQuery();

  const [activeTab, setActiveTab] = useState<number>(0);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);

  // Dialog States
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editName, setEditName] = useState('');
  const [editEmail, setEditEmail] = useState('');
  const [editRole, setEditRole] = useState('user');

  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [passwordOtp, setPasswordOtp] = useState('');

  const [tempTokenDialogOpen, setTempTokenDialogOpen] = useState(false);
  const [tempTokenRestorePasswd, setTempTokenRestorePasswd] = useState(false);
  const [tempTokenOtp, setTempTokenOtp] = useState('');
  const [issuedTempToken, setIssuedTempToken] = useState<string | null>(null);
  const [copiedToken, setCopiedToken] = useState(false);

  const [autoKillDialogOpen, setAutoKillDialogOpen] = useState(false);
  const [autoKillOtp, setAutoKillOtp] = useState('');

  const [permMatrixUser, setPermMatrixUser] = useState<AdminUser | null>(null);
  const [userPerms, setUserPerms] = useState<Record<string, boolean>>({});

  // Bulk Perm State
  const [bulkSelectedUserIds, setBulkSelectedUserIds] = useState<number[]>([]);
  const [bulkPerms, setBulkPerms] = useState<Record<string, boolean>>({});

  // Mutations
  const updateMutation = useUpdateUserMutation();
  const disableMutation = useDisableAccountMutation();
  const enableMutation = useEnableAccountMutation();
  const deleteMutation = useDeleteAccountMutation();
  const restoreMutation = useRestoreAccountMutation();
  const passwordMutation = useUpdatePasswordMutation();
  const tempTokenMutation = useTempTokenMutation();
  const resetKillMutation = useResetAutoKillMutation();
  const setPermsMutation = useSetPermissionsMutation();
  const removePermsMutation = useRemovePermissionsMutation();
  const bulkPermsMutation = useBulkSetPermissionsMutation();

  // Handlers
  const handleOpenEdit = (user: AdminUser) => {
    setSelectedUser(user);
    setEditName(user.name);
    setEditEmail(user.email);
    setEditRole(user.role || 'user');
    setEditDialogOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!selectedUser) return;
    await updateMutation.mutateAsync({
      userId: selectedUser.id,
      payload: { name: editName, email: editEmail, role: editRole },
    });
    setEditDialogOpen(false);
  };

  const handleOpenPassword = (user: AdminUser) => {
    setSelectedUser(user);
    setNewPassword('');
    setPasswordOtp('');
    setPasswordDialogOpen(true);
  };

  const handleSavePassword = async () => {
    if (!selectedUser || !newPassword) return;
    await passwordMutation.mutateAsync({
      userId: selectedUser.id,
      payload: { new_password: newPassword, otp: passwordOtp || undefined },
    });
    setPasswordDialogOpen(false);
  };

  const handleOpenTempToken = (user: AdminUser) => {
    setSelectedUser(user);
    setTempTokenRestorePasswd(false);
    setTempTokenOtp('');
    setIssuedTempToken(null);
    setTempTokenDialogOpen(true);
  };

  const handleGenerateTempToken = async () => {
    if (!selectedUser) return;
    const res = await tempTokenMutation.mutateAsync({
      userId: selectedUser.id,
      restorePasswd: tempTokenRestorePasswd,
      otp: tempTokenOtp || undefined,
    });
    setIssuedTempToken(res.temp_token || res.token || 'TOKEN_ISSUED_IN_COOKIE');
  };

  const handleOpenPermMatrix = (user: AdminUser) => {
    setPermMatrixUser(user);
    setUserPerms({ ...user.permissions });
    setActiveTab(1);
  };

  const handleTogglePerm = (perm: string) => {
    setUserPerms((prev) => ({
      ...prev,
      [perm]: !prev[perm],
    }));
  };

  const handleSaveUserPerms = async () => {
    if (!permMatrixUser) return;
    await setPermsMutation.mutateAsync({
      user_id: permMatrixUser.id,
      permissions: userPerms,
    });
  };

  const handleClearUserPerms = async () => {
    if (!permMatrixUser) return;
    await removePermsMutation.mutateAsync({
      user_id: permMatrixUser.id,
      remove_all: true,
    });
    setUserPerms({});
  };

  // Group permissions by category
  const permissionGroups = React.useMemo(() => {
    const groups: Record<string, string[]> = {};
    allPermissions.forEach((p) => {
      const parts = p.split('.');
      const category = parts[0] ? parts[0].toUpperCase() : 'GENERAL';
      if (!groups[category]) groups[category] = [];
      groups[category].push(p);
    });
    return groups;
  }, [allPermissions]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedToken(true);
    setTimeout(() => setCopiedToken(false), 2000);
  };

  return (
    <Box sx={{ p: 3, maxWidth: 1400, mx: 'auto' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 800, color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Settings sx={{ color: '#38BDF8' }} /> Admin Governance Console
          </Typography>
          <Typography variant="body2" sx={{ color: '#94A3B8', mt: 0.5 }}>
            Manage identity accounts, cryptographic roles, granular permissions, and kill-switch recovery.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshCw fontSize="small" />}
            onClick={() => refetchUsers()}
            sx={{ borderColor: '#334155', color: '#94A3B8', '&:hover': { borderColor: '#64748B' } }}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            color="error"
            startIcon={<ShieldAlert fontSize="small" />}
            onClick={() => setAutoKillDialogOpen(true)}
            sx={{ fontWeight: 700 }}
          >
            Reset Auto-Kill
          </Button>
        </Box>
      </Box>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: '#1E293B', mb: 3 }}>
        <Tabs value={activeTab} onChange={(_, val) => setActiveTab(val)} textColor="inherit">
          <Tab label="User Management & Security" icon={<Users fontSize="small" />} iconPosition="start" />
          <Tab
            label={permMatrixUser ? `Permissions (${permMatrixUser.email})` : 'Permission Matrix'}
            icon={<KeyRound fontSize="small" />}
            iconPosition="start"
          />
          <Tab label="Bulk Permission Matrix" icon={<Lock fontSize="small" />} iconPosition="start" />
        </Tabs>
      </Box>

      {/* TAB 0: USERS LIST */}
      {activeTab === 0 && (
        <Card sx={{ bgcolor: '#0B132B', border: '1px solid #1E293B', borderRadius: 2 }}>
          <CardContent sx={{ p: 0 }}>
            {usersLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 6 }}>
                <CircularProgress color="primary" />
              </Box>
            ) : (
              <TableContainer>
                <Table>
                  <TableHead sx={{ bgcolor: '#07111D' }}>
                    <TableRow>
                      <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>ID</TableCell>
                      <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>User / Email</TableCell>
                      <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Role</TableCell>
                      <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Status</TableCell>
                      <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>MFA</TableCell>
                      <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Permissions</TableCell>
                      <TableCell sx={{ color: '#94A3B8', fontWeight: 600, textAlign: 'right' }}>Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {users.map((u) => {
                      const permCount = Object.keys(u.permissions || {}).length;
                      return (
                        <TableRow key={u.id} sx={{ '&:hover': { bgcolor: '#0D1B3E' } }}>
                          <TableCell sx={{ color: '#64748B', fontFamily: 'monospace' }}>#{u.id}</TableCell>
                          <TableCell>
                            <Typography variant="body2" sx={{ fontWeight: 600, color: '#F8FAFC' }}>
                              {u.name || 'Unnamed'}
                            </Typography>
                            <Typography variant="caption" sx={{ color: '#94A3B8' }}>
                              {u.email}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={u.role.toUpperCase()}
                              size="small"
                              color={u.role === 'admin' ? 'secondary' : 'default'}
                              sx={{ fontWeight: 700, fontSize: 11 }}
                            />
                          </TableCell>
                          <TableCell>
                            {u.is_deleted ? (
                              <Chip label="Deleted" size="small" color="error" />
                            ) : u.disabled ? (
                              <Chip label="Disabled" size="small" color="warning" />
                            ) : (
                              <Chip label="Active" size="small" color="success" />
                            )}
                          </TableCell>
                          <TableCell>
                            {u.mfa_enabled ? (
                              <Chip label={u.mfa_method?.toUpperCase() || 'MFA'} size="small" color="info" />
                            ) : (
                              <Typography variant="caption" sx={{ color: '#64748B' }}>
                                None
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            <Button
                              size="small"
                              variant="text"
                              onClick={() => handleOpenPermMatrix(u)}
                              sx={{ textTransform: 'none', color: '#38BDF8', fontSize: 12 }}
                            >
                              {u.role === 'admin' ? 'Admin Full Access' : `${permCount} grants`}
                            </Button>
                          </TableCell>
                          <TableCell sx={{ textAlign: 'right' }}>
                            <Box sx={{ display: 'inline-flex', gap: 0.5 }}>
                              <Tooltip title="Edit Profile">
                                <IconButton size="small" onClick={() => handleOpenEdit(u)} sx={{ color: '#94A3B8' }}>
                                  <Edit fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="Reset Password">
                                <IconButton size="small" onClick={() => handleOpenPassword(u)} sx={{ color: '#94A3B8' }}>
                                  <Lock fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="Issue Temp Token (2 min SLT)">
                                <IconButton size="small" onClick={() => handleOpenTempToken(u)} sx={{ color: '#F59E0B' }}>
                                  <Clock fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              {u.disabled ? (
                                <Tooltip title="Enable Account">
                                  <IconButton
                                    size="small"
                                    onClick={() => enableMutation.mutate({ userId: u.id })}
                                    sx={{ color: '#10B981' }}
                                  >
                                    <UserCheck fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              ) : (
                                <Tooltip title="Disable Account">
                                  <IconButton
                                    size="small"
                                    onClick={() => disableMutation.mutate({ userId: u.id })}
                                    sx={{ color: '#EF4444' }}
                                  >
                                    <UserX fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              )}
                              {u.is_deleted ? (
                                <Tooltip title="Restore Account">
                                  <IconButton
                                    size="small"
                                    onClick={() => restoreMutation.mutate({ userId: u.id })}
                                    sx={{ color: '#10B981' }}
                                  >
                                    <RotateCcw fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              ) : (
                                <Tooltip title="Delete Account">
                                  <IconButton
                                    size="small"
                                    onClick={() => deleteMutation.mutate({ userId: u.id })}
                                    sx={{ color: '#64748B', '&:hover': { color: '#EF4444' } }}
                                  >
                                    <Trash2 fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              )}
                            </Box>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </CardContent>
        </Card>
      )}

      {/* TAB 1: PERMISSION MATRIX FOR SINGLE USER */}
      {activeTab === 1 && (
        <Card sx={{ bgcolor: '#0B132B', border: '1px solid #1E293B', borderRadius: 2, p: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Box>
              <Typography variant="h6" sx={{ color: '#F8FAFC', fontWeight: 700 }}>
                {permMatrixUser
                  ? `Assign Permissions: ${permMatrixUser.name} (${permMatrixUser.email})`
                  : 'Select a user to inspect and grant permissions'}
              </Typography>
              <Typography variant="body2" sx={{ color: '#94A3B8' }}>
                Fine-grained RBAC controls enforced at the API gateway and backend authorization dependencies.
              </Typography>
            </Box>
            {permMatrixUser && (
              <Box sx={{ display: 'flex', gap: 1.5 }}>
                <Button variant="outlined" color="error" size="small" onClick={handleClearUserPerms}>
                  Revoke All
                </Button>
                <Button
                  variant="contained"
                  color="primary"
                  size="small"
                  onClick={handleSaveUserPerms}
                  disabled={setPermsMutation.isPending}
                >
                  Save Permissions
                </Button>
              </Box>
            )}
          </Box>

          {!permMatrixUser ? (
            <Alert severity="info" sx={{ bgcolor: '#07111D', color: '#94A3B8', border: '1px solid #1E293B' }}>
              Please select a user from the "User Management" tab or click their permissions chip.
            </Alert>
          ) : (
            <Grid container spacing={3}>
              {Object.entries(permissionGroups).map(([category, perms]) => (
                <Grid item xs={12} md={6} lg={4} key={category}>
                  <Paper
                    sx={{
                      p: 2,
                      bgcolor: '#07111D',
                      border: '1px solid #1E293B',
                      borderRadius: 2,
                      height: '100%',
                    }}
                  >
                    <Typography variant="subtitle2" sx={{ color: '#38BDF8', fontWeight: 700, mb: 1.5 }}>
                      {category}
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                      {perms.map((perm) => (
                        <FormControlLabel
                          key={perm}
                          control={
                            <Checkbox
                              checked={Boolean(userPerms[perm])}
                              onChange={() => handleTogglePerm(perm)}
                              size="small"
                              sx={{ color: '#475569', '&.Mui-checked': { color: '#38BDF8' } }}
                            />
                          }
                          label={
                            <Typography variant="caption" sx={{ color: '#E2E8F0', fontFamily: 'monospace' }}>
                              {perm}
                            </Typography>
                          }
                        />
                      ))}
                    </Box>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          )}
        </Card>
      )}

      {/* TAB 2: BULK PERMISSION MATRIX */}
      {activeTab === 2 && (
        <Card sx={{ bgcolor: '#0B132B', border: '1px solid #1E293B', borderRadius: 2, p: 3 }}>
          <Typography variant="h6" sx={{ color: '#F8FAFC', fontWeight: 700, mb: 1 }}>
            Bulk Permission Delegation
          </Typography>
          <Typography variant="body2" sx={{ color: '#94A3B8', mb: 3 }}>
            Select multiple target user accounts and apply a standardized set of permissions simultaneously.
          </Typography>

          <Grid container spacing={3}>
            {/* Target Users Column */}
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, bgcolor: '#07111D', border: '1px solid #1E293B', borderRadius: 2 }}>
                <Typography variant="subtitle2" sx={{ color: '#38BDF8', fontWeight: 700, mb: 1.5 }}>
                  Select Target Users ({bulkSelectedUserIds.length})
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, maxHeight: 400, overflowY: 'auto' }}>
                  {users.map((u) => {
                    const isSelected = bulkSelectedUserIds.includes(u.id);
                    return (
                      <FormControlLabel
                        key={u.id}
                        control={
                          <Checkbox
                            checked={isSelected}
                            onChange={() => {
                              if (isSelected) {
                                setBulkSelectedUserIds((prev) => prev.filter((id) => id !== u.id));
                              } else {
                                setBulkSelectedUserIds((prev) => [...prev, u.id]);
                              }
                            }}
                            size="small"
                            sx={{ color: '#475569', '&.Mui-checked': { color: '#38BDF8' } }}
                          />
                        }
                        label={
                          <Typography variant="caption" sx={{ color: '#E2E8F0' }}>
                            {u.name} ({u.email})
                          </Typography>
                        }
                      />
                    );
                  })}
                </Box>
              </Paper>
            </Grid>

            {/* Permissions Column */}
            <Grid item xs={12} md={8}>
              <Paper sx={{ p: 2, bgcolor: '#07111D', border: '1px solid #1E293B', borderRadius: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Typography variant="subtitle2" sx={{ color: '#38BDF8', fontWeight: 700 }}>
                    Select Permissions to Assign
                  </Typography>
                  <Button
                    variant="contained"
                    color="primary"
                    disabled={bulkSelectedUserIds.length === 0 || bulkPermsMutation.isPending}
                    onClick={async () => {
                      const payload = {
                        all_user_permissions: bulkSelectedUserIds.map((userId) => ({
                          user_id: userId,
                          permissions: bulkPerms,
                        })),
                      };
                      await bulkPermsMutation.mutateAsync(payload);
                    }}
                  >
                    Apply Bulk Permissions
                  </Button>
                </Box>

                <Grid container spacing={2}>
                  {Object.entries(permissionGroups).map(([category, perms]) => (
                    <Grid item xs={12} sm={6} key={category}>
                      <Typography variant="caption" sx={{ color: '#94A3B8', fontWeight: 700 }}>
                        {category}
                      </Typography>
                      {perms.map((perm) => (
                        <FormControlLabel
                          key={perm}
                          control={
                            <Checkbox
                              checked={Boolean(bulkPerms[perm])}
                              onChange={() =>
                                setBulkPerms((prev) => ({
                                  ...prev,
                                  [perm]: !prev[perm],
                                }))
                              }
                              size="small"
                              sx={{ color: '#475569', '&.Mui-checked': { color: '#38BDF8' } }}
                            />
                          }
                          label={
                            <Typography variant="caption" sx={{ color: '#E2E8F0', fontFamily: 'monospace' }}>
                              {perm}
                            </Typography>
                          }
                          sx={{ display: 'block', m: 0 }}
                        />
                      ))}
                    </Grid>
                  ))}
                </Grid>
              </Paper>
            </Grid>
          </Grid>
        </Card>
      )}

      {/* EDIT USER DIALOG */}
      <Dialog open={editDialogOpen} onClose={() => setEditDialogOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#F8FAFC' }}>Edit User Account</DialogTitle>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField
            label="Name"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            fullWidth
            size="small"
            sx={{ mt: 1 }}
          />
          <TextField
            label="Email"
            value={editEmail}
            onChange={(e) => setEditEmail(e.target.value)}
            fullWidth
            size="small"
          />
          <TextField
            select
            label="Role"
            value={editRole}
            onChange={(e) => setEditRole(e.target.value)}
            fullWidth
            size="small"
          >
            <MenuItem value="user">User (Standard)</MenuItem>
            <MenuItem value="admin">Administrator</MenuItem>
          </TextField>
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button onClick={() => setEditDialogOpen(false)} sx={{ color: '#94A3B8' }}>
            Cancel
          </Button>
          <Button variant="contained" onClick={handleSaveEdit} disabled={updateMutation.isPending}>
            Save Changes
          </Button>
        </DialogActions>
      </Dialog>

      {/* RESET PASSWORD DIALOG */}
      <Dialog open={passwordDialogOpen} onClose={() => setPasswordDialogOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#F8FAFC', display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
          <Typography variant="h6" fontWeight={700}>Update User Password</Typography>
          <IconButton size="small" onClick={() => setPasswordDialogOpen(false)} sx={{ color: '#94A3B8', '&:hover': { color: '#EF4444' } }}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField
            label="New Password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            fullWidth
            size="small"
            sx={{ mt: 1 }}
          />
          {isMFAEnabled && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="caption" sx={{ color: '#38BDF8', fontWeight: 700, display: 'block', textAlign: 'center', mb: 0.5 }}>
                Admin MFA Authorization Code (6 Digits)
              </Typography>
              <OtpBoxesInput
                value={passwordOtp}
                onChange={setPasswordOtp}
              />
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button onClick={() => setPasswordDialogOpen(false)} sx={{ color: '#94A3B8' }}>
            Cancel
          </Button>
          <Button variant="contained" onClick={handleSavePassword} disabled={passwordMutation.isPending || !newPassword}>
            Update Password
          </Button>
        </DialogActions>
      </Dialog>

      {/* ISSUE TEMP TOKEN DIALOG */}
      <Dialog open={tempTokenDialogOpen} onClose={() => setTempTokenDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#F8FAFC', display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
          <Typography variant="h6" fontWeight={700}>Issue Temporary Token (SLT)</Typography>
          <IconButton size="small" onClick={() => setTempTokenDialogOpen(false)} sx={{ color: '#94A3B8', '&:hover': { color: '#EF4444' } }}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="body2" sx={{ color: '#94A3B8', mt: 1 }}>
            Issues a 2-minute Short-Lived Token (SLT) that allows the target user to reset password or restore accounts.
          </Typography>

          <FormControlLabel
            control={
              <Checkbox
                checked={tempTokenRestorePasswd}
                onChange={(e) => setTempTokenRestorePasswd(e.target.checked)}
                sx={{ color: '#475569', '&.Mui-checked': { color: '#38BDF8' } }}
              />
            }
            label={<Typography variant="body2" sx={{ color: '#F8FAFC' }}>Allow Password Restoration</Typography>}
          />

          {isMFAEnabled && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="caption" sx={{ color: '#38BDF8', fontWeight: 700, display: 'block', textAlign: 'center', mb: 0.5 }}>
                Admin MFA Authorization Code (6 Digits)
              </Typography>
              <OtpBoxesInput
                value={tempTokenOtp}
                onChange={setTempTokenOtp}
              />
            </Box>
          )}

          {issuedTempToken && (
            <Paper sx={{ p: 2, bgcolor: '#07111D', border: '1px solid #1E293B', borderRadius: 1 }}>
              <Typography variant="caption" sx={{ color: '#38BDF8', fontWeight: 700, display: 'block', mb: 1 }}>
                Issued Short-Lived Token (Expires in 120s):
              </Typography>
              <Typography
                variant="body2"
                sx={{
                  fontFamily: 'monospace',
                  wordBreak: 'break-all',
                  color: '#A7F3D0',
                  fontSize: 12,
                  bgcolor: '#030712',
                  p: 1.5,
                  borderRadius: 1,
                }}
              >
                {issuedTempToken}
              </Typography>
              <Button
                variant="outlined"
                size="small"
                startIcon={copiedToken ? <Check fontSize="small" /> : <Copy fontSize="small" />}
                onClick={() => copyToClipboard(issuedTempToken)}
                sx={{ mt: 1.5, color: '#38BDF8', borderColor: '#38BDF8' }}
              >
                {copiedToken ? 'Copied' : 'Copy Token'}
              </Button>
            </Paper>
          )}
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button onClick={() => setTempTokenDialogOpen(false)} sx={{ color: '#94A3B8' }}>
            Close
          </Button>
          {!issuedTempToken && (
            <Button
              variant="contained"
              onClick={handleGenerateTempToken}
              disabled={tempTokenMutation.isPending}
            >
              Generate Token
            </Button>
          )}
        </DialogActions>
      </Dialog>

      {/* RESET AUTO-KILL DIALOG */}
      <Dialog open={autoKillDialogOpen} onClose={() => setAutoKillDialogOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#EF4444', display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ShieldAlert fontSize="medium" /> Reset Auto-Kill Safety Switch
          </Box>
          <IconButton size="small" onClick={() => setAutoKillDialogOpen(false)} sx={{ color: '#94A3B8', '&:hover': { color: '#EF4444' } }}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="body2" sx={{ color: '#94A3B8', mt: 1 }}>
            This clears the Redis safety mode flag that halts system endpoints after repeated critical internal failures.
          </Typography>
          {isMFAEnabled && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="caption" sx={{ color: '#EF4444', fontWeight: 700, display: 'block', textAlign: 'center', mb: 0.5 }}>
                Safety Switch Authorization Code (6 Digits)
              </Typography>
              <OtpBoxesInput
                value={autoKillOtp}
                onChange={setAutoKillOtp}
              />
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button onClick={() => setAutoKillDialogOpen(false)} sx={{ color: '#94A3B8' }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={async () => {
              await resetKillMutation.mutateAsync(autoKillOtp || undefined);
              setAutoKillDialogOpen(false);
            }}
            disabled={resetKillMutation.isPending}
          >
            Confirm Reset
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AdminPage;
