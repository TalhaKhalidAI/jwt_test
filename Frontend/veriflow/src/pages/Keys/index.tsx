// src/pages/Keys/index.tsx
import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Tooltip,
  Paper,
  Stack,
  Alert,
  Tabs,
  Tab,
} from '@mui/material';
import {
  AddRounded as AddIcon,
  AutorenewRounded as RotateIcon,
  BlockRounded as RevokeIcon,
  ContentCopyRounded as CopyIcon,
  QrCode2Rounded as QrCodeIcon,
  VpnKeyRounded as KeyIcon,
  VisibilityRounded as VisibilityIcon,
  DownloadRounded as DownloadIcon,
  CheckCircleOutlineRounded as VerifyIcon,
  SendRounded as IssueIcon,
  SecurityRounded as SecurityIcon,
} from '@mui/icons-material';
import {
  useKeysQuery,
  useJWKSQuery,
  useCreateKeyMutation,
  useRotateKeyMutation,
  useRevokeKeyMutation,
  useExportPrivateKeyMutation,
  useIssueTokenMutation,
  useVerifyTokenMutation,
  useGenerateTagQRMutation,
} from './query';
import { useMFAStatusQuery } from '../Security/query';
import type { KeyRecord, VerifyTokenResponse } from './types';
import { ToastMsgs } from '../../api/toastUtils';
import { http } from '../../api/http/https';
import { useAuthStore } from '../../store/authStore';
import { OtpBoxesInput } from '../../components/OtpModal';
import { CloseRounded as CloseIcon } from '@mui/icons-material';

export function KeysPage() {
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.role === 'admin' || user?.user_role === 'admin';
  const canCreateKey = isAdmin || Boolean(user?.permissions?.['keys.create']);
  const canRotateKey = isAdmin || (Boolean(user?.permissions?.['keys.create']) && Boolean(user?.permissions?.['keys.update']));
  const canRevokeKey = isAdmin || Boolean(user?.permissions?.['keys.revoke']);
  const canIssueToken = isAdmin || Boolean(user?.permissions?.["keys.create"]);
  const canCreateTags = isAdmin || Boolean(user?.permissions?.["tags.create"]);

  const { data: keysData, isLoading } = useKeysQuery();
  const { data: jwksData } = useJWKSQuery();
  const { data: mfaStatus } = useMFAStatusQuery();
  const isMFAEnabled = Boolean(user?.mfa_enabled || mfaStatus?.mfa_enabled);
  const activeMFAMethod = user?.mfa_method || mfaStatus?.mfa_method || "totp";

  const createKeyMutation = useCreateKeyMutation();
  const rotateKeyMutation = useRotateKeyMutation();
  const revokeKeyMutation = useRevokeKeyMutation();
  const exportPrivateMutation = useExportPrivateKeyMutation();
  const issueTokenMutation = useIssueTokenMutation();
  const verifyTokenMutation = useVerifyTokenMutation();
  const generateTagMutation = useGenerateTagQRMutation();

  // Modals state
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [rotateModalOpen, setRotateModalOpen] = useState(false);
  const [revokeModalOpen, setRevokeModalOpen] = useState(false);
  const [selectedKeyForRevoke, setSelectedKeyForRevoke] = useState<KeyRecord | null>(null);

  const [pemModalOpen, setPemModalOpen] = useState(false);
  const [selectedKeyForPem, setSelectedKeyForPem] = useState<KeyRecord | null>(null);

  const [privatePemModalOpen, setPrivatePemModalOpen] = useState(false);
  const [exportAuthModalOpen, setExportAuthModalOpen] = useState(false);
  const [targetKeyForExport, setTargetKeyForExport] = useState<KeyRecord | null>(null);
  const [exportPassword, setExportPassword] = useState("");
  const [exportOtp, setExportOtp] = useState("");
  const [isSendingOtp, setIsSendingOtp] = useState(false);
  const [privatePemResult, setPrivatePemResult] = useState<string | null>(null);

  const [jwksModalOpen, setJwksModalOpen] = useState(false);
  const [issueTokenModalOpen, setIssueTokenModalOpen] = useState(false);
  const [issuedTokenResult, setIssuedTokenResult] = useState<string | null>(null);

  const [verifyModalOpen, setVerifyModalOpen] = useState(false);
  const [verifyTokenInput, setVerifyTokenInput] = useState('');
  const [verifyResult, setVerifyResult] = useState<VerifyTokenResponse | null>(null);

  const [tagModalOpen, setTagModalOpen] = useState(false);
  const [tagTab, setTagTab] = useState<number>(0);
  const [tagVerifyInput, setTagVerifyInput] = useState('');
  const [tagVerifyResult, setTagVerifyResult] = useState<VerifyTokenResponse | null>(null);

  // Forms
  const [createForm, setCreateForm] = useState({ name: '', kid: '', key_size: 2048, target_user_id: '' });
  const [rotateForm, setRotateForm] = useState({ name: '', key_size: 2048 });
  const [revokeReason, setRevokeReason] = useState('');

  const [issueForm, setIssueForm] = useState({
    key_id: '',
    target_user_id: '',
    expires_in_minutes: 480,
    extra_claims: '{\n  "work_station": "BAY-4"\n}',
  });

  const [tagForm, setTagForm] = useState({
    sku: 'SKU-99201',
    batch: 'BATCH-2026-X',
    warehouse: 'WH-CENTRAL-01',
    key_id: '',
    duration: 30,
    unit: 'days' as 'days' | 'hours' | 'minutes' | 'weeks' | 'months',
    qr_only: false,
  });

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    ToastMsgs.info(`${label} copied to clipboard!`);
  };

  const handleDownloadQR = (base64Url: string, filename: string) => {
    const a = document.createElement('a');
    a.href = base64Url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const handleCreateSubmit = async () => {
    if (!createForm.name.trim()) {
      ToastMsgs.error('Key Name is required');
      return;
    }
    await createKeyMutation.mutateAsync({
      name: createForm.name,
      kid: createForm.kid.trim() || undefined,
      key_size: createForm.key_size,
      target_user_id: createForm.target_user_id ? Number(createForm.target_user_id) : undefined,
    });
    setCreateModalOpen(false);
    setCreateForm({ name: '', kid: '', key_size: 2048, target_user_id: '' });
  };

  const handleRotateSubmit = async () => {
    if (!rotateForm.name.trim()) {
      ToastMsgs.error('Rotation Key Name is required');
      return;
    }
    await rotateKeyMutation.mutateAsync({
      name: rotateForm.name,
      key_size: rotateForm.key_size,
    });
    setRotateModalOpen(false);
    setRotateForm({ name: '', key_size: 2048 });
  };

  const handleRevokeSubmit = async () => {
    if (!selectedKeyForRevoke || !revokeReason.trim()) {
      ToastMsgs.error('Revocation reason is required');
      return;
    }
    await revokeKeyMutation.mutateAsync({
      keyId: selectedKeyForRevoke.id,
      payload: { reason: revokeReason },
    });
    setRevokeModalOpen(false);
    setSelectedKeyForRevoke(null);
    setRevokeReason('');
  };

  const handleOpenExportAuth = (k: KeyRecord) => {
    setTargetKeyForExport(k);
    setExportPassword("");
    setExportOtp("");
    setExportAuthModalOpen(true);
  };

  const handleConfirmExport = async () => {
    if (!targetKeyForExport || !exportPassword) return;
    try {
      const res = await exportPrivateMutation.mutateAsync({
        keyId: targetKeyForExport.id,
        password: exportPassword,
        otp: exportOtp.trim() || undefined,
      });
      setPrivatePemResult(res.private_key);
      setExportAuthModalOpen(false);
      setPrivatePemModalOpen(true);
    } catch {
      // toast shown in query
    }
  };

  const handleIssueToken = async () => {
    let claims = {};
    try {
      if (issueForm.extra_claims.trim()) {
        claims = JSON.parse(issueForm.extra_claims);
      }
    } catch {
      ToastMsgs.error('Extra claims must be valid JSON');
      return;
    }

    const res = await issueTokenMutation.mutateAsync({
      key_id: issueForm.key_id || undefined,
      target_user_id: issueForm.target_user_id ? Number(issueForm.target_user_id) : undefined,
      expires_in_minutes: Number(issueForm.expires_in_minutes),
      extra_claims: claims,
    });
    setIssuedTokenResult(res.token);
  };

  const handleVerifyToken = async (tokenString: string) => {
    if (!tokenString.trim()) return;
    try {
      const res = await verifyTokenMutation.mutateAsync({ token: tokenString.trim() });
      setVerifyResult(res);
    } catch (err: any) {
      setVerifyResult({
        status: 'error',
        valid: false,
        message: err?.response?.data?.detail || err?.message || 'Verification failed',
      });
    }
  };

  const handleGenerateTag = async () => {
    await generateTagMutation.mutateAsync({
      key_id: tagForm.key_id || undefined,
      payload: {
        sku: tagForm.sku,
        batch_no: tagForm.batch,
        warehouse_id: tagForm.warehouse,
      },
      expires_in_value: tagForm.duration,
      expires_in_unit: tagForm.unit,
      box_size: 10,
      border: 4,
      format: 'json',
    });
  };

  const handleVerifyTag = async () => {
    if (!tagVerifyInput.trim()) return;
    try {
      const res = await verifyTokenMutation.mutateAsync({ token: tagVerifyInput.trim() });
      setTagVerifyResult(res);
    } catch (err: any) {
      setTagVerifyResult({
        status: 'error',
        valid: false,
        message: err?.response?.data?.detail || err?.message || 'Tag verification failed',
      });
    }
  };

  const keys = keysData?.items || [];

  return (
    <Box sx={{ maxWidth: 1400, mx: 'auto', p: { xs: 2, sm: 3 } }}>
      {/* Top Banner */}
      <Box
        sx={{
          mb: 4,
          display: 'flex',
          flexDirection: { xs: 'column', md: 'row' },
          justifyContent: 'space-between',
          alignItems: { xs: 'flex-start', md: 'center' },
          gap: 2,
        }}
      >
        <Box>
          <Typography variant="h4" fontWeight={800} sx={{ color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <KeyIcon sx={{ color: '#38BDF8', fontSize: 36 }} />
            Cryptographic Keys & Asymmetric Engine
          </Typography>
          <Typography variant="body2" sx={{ color: '#94A3B8', mt: 0.5 }}>
            Manage RSA keypairs, sign offline tokens, inspect JWKS, and issue RS256-signed product tag QR codes.
          </Typography>
        </Box>

        <Stack direction="row" spacing={1.5} flexWrap="wrap">
          <Button
            variant="outlined"
            startIcon={<VerifyIcon />}
            onClick={() => {
              setVerifyResult(null);
              setVerifyTokenInput('');
              setVerifyModalOpen(true);
            }}
            sx={{ borderColor: '#334155', color: '#38BDF8' }}
          >
            Verify RS256 Token
          </Button>

          {canIssueToken && (
            <Button
              variant="outlined"
              startIcon={<IssueIcon />}
              onClick={() => {
                setIssuedTokenResult(null);
                setIssueTokenModalOpen(true);
              }}
              sx={{ borderColor: '#334155', color: '#10B981' }}
            >
              Issue RS256 Token
            </Button>
          )}

          {canCreateTags && (
            <Button
              variant="outlined"
              startIcon={<QrCodeIcon />}
              onClick={() => setTagModalOpen(true)}
              sx={{ borderColor: '#FACC15', color: '#FACC15', '&:hover': { bgcolor: 'rgba(250, 204, 21, 0.1)' } }}
            >
              Product Tag QR
            </Button>
          )}

          <Button
            variant="outlined"
            startIcon={<VisibilityIcon />}
            onClick={() => setJwksModalOpen(true)}
            sx={{ borderColor: '#334155', color: '#94A3B8' }}
          >
            JWKS
          </Button>

          {canRotateKey && (
            <Button
              variant="contained"
              startIcon={<RotateIcon />}
              onClick={() => setRotateModalOpen(true)}
              sx={{ bgcolor: '#10B981', '&:hover': { bgcolor: '#059669' } }}
            >
              Rotate Key
            </Button>
          )}

          {canCreateKey && (
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setCreateModalOpen(true)}
              sx={{ bgcolor: '#2563EB', '&:hover': { bgcolor: '#1D4ED8' } }}
            >
              Generate Key
            </Button>
          )}
        </Stack>
      </Box>

      {/* Keys Table Card */}
      <Card sx={{ bgcolor: '#0B132B', border: '1px solid #1E293B', borderRadius: 3 }}>
        <CardContent sx={{ p: 0 }}>
          <TableContainer>
            <Table>
              <TableHead sx={{ bgcolor: '#07111D' }}>
                <TableRow>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Key ID (kid)</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Name / Description</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Status</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Created</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600, textAlign: 'right' }}>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} align="center" sx={{ py: 6 }}>
                      <CircularProgress color="primary" />
                    </TableCell>
                  </TableRow>
                ) : keys.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} align="center" sx={{ py: 6, color: '#94A3B8' }}>
                      No cryptographic keys generated yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  keys.map((k) => {
                    const isActive = k.status === 'active';
                    return (
                      <TableRow key={k.id} sx={{ '&:hover': { bgcolor: '#0D1B3E' } }}>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 700, color: '#38BDF8' }}>
                            {k.kid}
                          </Typography>
                          <Typography variant="caption" sx={{ color: '#64748B' }}>
                            UUID: {k.id.slice(0, 8)}...
                          </Typography>
                        </TableCell>

                        <TableCell>
                          <Typography variant="body2" sx={{ fontWeight: 600, color: '#F8FAFC' }}>
                            {k.name}
                          </Typography>
                          <Typography variant="caption" sx={{ color: '#94A3B8' }}>
                            RSA-2048 / RS256
                          </Typography>
                        </TableCell>

                        <TableCell>
                          <Chip
                            label={k.status.toUpperCase()}
                            size="small"
                            color={isActive ? 'success' : 'error'}
                            sx={{ fontWeight: 700, fontSize: 11 }}
                          />
                        </TableCell>

                        <TableCell>
                          <Typography variant="body2" sx={{ color: '#94A3B8' }}>
                            {k.created_at ? new Date(k.created_at).toLocaleDateString() : 'N/A'}
                          </Typography>
                        </TableCell>

                        <TableCell align="right">
                          <Stack direction="row" spacing={1} justifyContent="flex-end">
                            <Tooltip title="View Public Key PEM">
                              <IconButton
                                size="small"
                                onClick={() => {
                                  setSelectedKeyForPem(k);
                                  setPemModalOpen(true);
                                }}
                                sx={{ color: '#38BDF8' }}
                              >
                                <VisibilityIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>

                            {isAdmin && (
                              <Tooltip title="Export Decrypted Private Key (Admin Only)">
                                <IconButton
                                  size="small"
                                  onClick={() => handleOpenExportAuth(k)}
                                  sx={{ color: '#F59E0B' }}
                                >
                                  <SecurityIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}

                            {isActive && canRevokeKey && (
                              <Tooltip title="Revoke Key">
                                <IconButton
                                  size="small"
                                  onClick={() => {
                                    setSelectedKeyForRevoke(k);
                                    setRevokeModalOpen(true);
                                  }}
                                  sx={{ color: '#EF4444' }}
                                >
                                  <RevokeIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                          </Stack>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* CREATE KEY MODAL */}
      <Dialog open={createModalOpen} onClose={() => setCreateModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#F8FAFC' }}>Generate Asymmetric Keypair</DialogTitle>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField
            label="Key Name"
            placeholder="e.g. Warehouse Main RS256"
            value={createForm.name}
            onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
            fullWidth
            size="small"
            sx={{ mt: 1 }}
          />
          <TextField
            label="Custom Key ID (kid) - Optional"
            placeholder="e.g. wh-us-east-01"
            value={createForm.kid}
            onChange={(e) => setCreateForm({ ...createForm, kid: e.target.value })}
            fullWidth
            size="small"
            helperText="Leave empty to auto-generate a unique timestamped kid"
          />
          {isAdmin && (
            <TextField
              label="Target User ID (Admin Delegation) - Optional"
              placeholder="e.g. 2"
              value={createForm.target_user_id}
              onChange={(e) => setCreateForm({ ...createForm, target_user_id: e.target.value })}
              fullWidth
              size="small"
            />
          )}
          <FormControl fullWidth size="small">
            <InputLabel>Key Bit Size</InputLabel>
            <Select
              value={createForm.key_size}
              label="Key Bit Size"
              onChange={(e) => setCreateForm({ ...createForm, key_size: Number(e.target.value) })}
            >
              <MenuItem value={2048}>2048 bits (Standard & Fast)</MenuItem>
              <MenuItem value={4096}>4096 bits (Highest Security)</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button onClick={() => setCreateModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Cancel
          </Button>
          <Button variant="contained" onClick={handleCreateSubmit} disabled={createKeyMutation.isPending}>
            Generate Keypair
          </Button>
        </DialogActions>
      </Dialog>

      {/* ROTATE KEY MODAL */}
      <Dialog open={rotateModalOpen} onClose={() => setRotateModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#F8FAFC' }}>Rotate Active Key</DialogTitle>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Alert severity="warning" sx={{ mt: 1 }}>
            Rotating generates a new primary signing key. Previous keys remain valid for verification until revoked.
          </Alert>
          <TextField
            label="Rotation Key Name"
            value={rotateForm.name}
            onChange={(e) => setRotateForm({ ...rotateForm, name: e.target.value })}
            fullWidth
            size="small"
          />
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button onClick={() => setRotateModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Cancel
          </Button>
          <Button variant="contained" color="success" onClick={handleRotateSubmit} disabled={rotateKeyMutation.isPending}>
            Confirm Rotation
          </Button>
        </DialogActions>
      </Dialog>

      {/* REVOKE KEY MODAL */}
      <Dialog open={revokeModalOpen} onClose={() => setRevokeModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#EF4444' }}>Revoke Cryptographic Key</DialogTitle>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="body2" sx={{ color: '#94A3B8', mt: 1 }}>
            Revoking key <strong>{selectedKeyForRevoke?.kid}</strong> prevents it from issuing new tokens.
          </Typography>
          <TextField
            label="Audit Reason"
            value={revokeReason}
            onChange={(e) => setRevokeReason(e.target.value)}
            fullWidth
            multiline
            rows={2}
          />
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button onClick={() => setRevokeModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Cancel
          </Button>
          <Button variant="contained" color="error" onClick={handleRevokeSubmit} disabled={revokeKeyMutation.isPending}>
            Revoke Key
          </Button>
        </DialogActions>
      </Dialog>

      {/* VIEW PUBLIC KEY PEM */}
      <Dialog open={pemModalOpen} onClose={() => setPemModalOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#F8FAFC' }}>
          Public Key PEM: {selectedKeyForPem?.kid}
        </DialogTitle>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 2 }}>
          <Paper sx={{ p: 2, bgcolor: '#07111D', border: '1px solid #1E293B', borderRadius: 2 }}>
            <Typography component="pre" sx={{ fontFamily: 'monospace', fontSize: 12, color: '#38BDF8', m: 0 }}>
              {selectedKeyForPem?.public_key}
            </Typography>
          </Paper>
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button
            startIcon={<CopyIcon />}
            variant="outlined"
            onClick={() => handleCopy(selectedKeyForPem?.public_key || '', 'Public Key PEM')}
            sx={{ color: '#38BDF8', borderColor: '#38BDF8' }}
          >
            Copy PEM
          </Button>
          <Button onClick={() => setPemModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* STEP-UP AUTHENTICATION DIALOG (PASSWORD + MFA) */}
      <Dialog
        open={exportAuthModalOpen}
        onClose={() => setExportAuthModalOpen(false)}
        maxWidth="xs"
        fullWidth
        PaperProps={{
          sx: { bgcolor: "#0B132B", color: "#F8FAFC", border: "1px solid #EF4444", borderRadius: 3 },
        }}
      >
        <DialogTitle sx={{ color: "#EF4444", display: "flex", alignItems: "center", justifyContent: "space-between", pb: 1 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <SecurityIcon /> Step-Up Verification Required
          </Box>
          <IconButton
            size="small"
            onClick={() => setExportAuthModalOpen(false)}
            sx={{ color: "#94A3B8", "&:hover": { color: "#EF4444", bgcolor: "rgba(239, 68, 68, 0.1)" } }}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ pt: 2, display: "flex", flexDirection: "column", gap: 2 }}>
          <Alert severity="warning" sx={{ bgcolor: "rgba(234, 179, 8, 0.1)", color: "#FACC15", border: "1px solid rgba(234, 179, 8, 0.3)" }}>
            High-Security Action: Exporting private key <strong>{targetKeyForExport?.kid}</strong>.
          </Alert>

          <TextField
            autoFocus
            label="Account Password"
            type="password"
            value={exportPassword}
            onChange={(e) => setExportPassword(e.target.value)}
            fullWidth
            size="small"
            placeholder="Enter your account password"
            sx={{
              mt: 1,
              "& .MuiOutlinedInput-root": {
                bgcolor: "#07111D",
              },
            }}
          />

          {isMFAEnabled ? (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
              <Typography variant="caption" sx={{ color: "#38BDF8", fontWeight: 700, textAlign: "center" }}>
                {activeMFAMethod === "totp"
                  ? "Enter 6-Digit Authenticator Code (TOTP)"
                  : "Enter 6-Digit Email OTP Security Code"}
              </Typography>
              <OtpBoxesInput
                value={exportOtp}
                onChange={setExportOtp}
              />
              {activeMFAMethod === "email" && (
                <Button
                  size="small"
                  variant="outlined"
                  onClick={async () => {
                    setIsSendingOtp(true);
                    try {
                      await http.post("/mfa/send_genaric_otp?purpose=mfa_stepup");
                      ToastMsgs.info("Security code sent to your email.");
                    } catch (err: any) {
                      ToastMsgs.error(err?.message || "Failed to send email code");
                    } finally {
                      setIsSendingOtp(false);
                    }
                  }}
                  disabled={isSendingOtp}
                  sx={{ color: "#38BDF8", borderColor: "#38BDF8" }}
                >
                  {isSendingOtp ? "Sending Code..." : "Send Code to My Email"}
                </Button>
              )}
            </Box>
          ) : (
            <Alert severity="info" sx={{ bgcolor: "rgba(56, 189, 248, 0.1)", color: "#38BDF8", border: "1px solid rgba(56, 189, 248, 0.3)", py: 0.5 }}>
              Two-factor authentication is not active on your profile. Password verification alone is required.
            </Alert>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setExportAuthModalOpen(false)} sx={{ color: "#94A3B8" }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleConfirmExport}
            disabled={!exportPassword || (isMFAEnabled && exportOtp.length !== 6) || exportPrivateMutation.isPending}
          >
            {exportPrivateMutation.isPending ? <CircularProgress size={20} /> : "Verify & Export Key"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* VIEW DECRYPTED PRIVATE KEY PEM (ADMIN ONLY) */}
      <Dialog open={privatePemModalOpen} onClose={() => setPrivatePemModalOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#EF4444', display: 'flex', alignItems: 'center', gap: 1 }}>
          <SecurityIcon /> Decrypted Private Key PEM (Confidential)
        </DialogTitle>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 2 }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            CRITICAL SECURITY MATERIAL: This decrypted RSA private key can sign tokens as this authority.
          </Alert>
          <Paper sx={{ p: 2, bgcolor: '#07111D', border: '1px solid #7F1D1D', borderRadius: 2 }}>
            <Typography component="pre" sx={{ fontFamily: 'monospace', fontSize: 12, color: '#FCA5A5', m: 0 }}>
              {privatePemResult}
            </Typography>
          </Paper>
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button
            startIcon={<CopyIcon />}
            variant="outlined"
            onClick={() => handleCopy(privatePemResult || '', 'Private Key PEM')}
            sx={{ color: '#EF4444', borderColor: '#EF4444' }}
          >
            Copy Private Key
          </Button>
          <Button onClick={() => setPrivatePemModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* JWKS MODAL */}
      <Dialog open={jwksModalOpen} onClose={() => setJwksModalOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#F8FAFC' }}>JSON Web Key Set (JWKS)</DialogTitle>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 2 }}>
          <Paper sx={{ p: 2, bgcolor: '#07111D', border: '1px solid #1E293B', borderRadius: 2 }}>
            <Typography component="pre" sx={{ fontFamily: 'monospace', fontSize: 12, color: '#34D399', m: 0 }}>
              {JSON.stringify(jwksData || { keys: [] }, null, 2)}
            </Typography>
          </Paper>
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button
            startIcon={<CopyIcon />}
            variant="outlined"
            onClick={() => handleCopy(JSON.stringify(jwksData || {}, null, 2), 'JWKS')}
            sx={{ color: '#34D399', borderColor: '#34D399' }}
          >
            Copy JWKS
          </Button>
          <Button onClick={() => setJwksModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* ISSUE TOKEN MODAL */}
      <Dialog open={issueTokenModalOpen} onClose={() => setIssueTokenModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#F8FAFC' }}>Issue RS256 Asymmetric JWT</DialogTitle>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="body2" sx={{ color: '#94A3B8', mt: 1 }}>
            Sign arbitrary claims using the database RSA private key. Scanners verify this offline using the public key.
          </Typography>

          <TextField
            select
            label="Signing Key"
            value={issueForm.key_id}
            onChange={(e) => setIssueForm({ ...issueForm, key_id: e.target.value })}
            fullWidth
            size="small"
          >
            <MenuItem value="">Latest Active Key (Auto-detect)</MenuItem>
            {keys.map((k) => (
              <MenuItem key={k.id} value={k.id}>
                {k.name} ({k.kid})
              </MenuItem>
            ))}
          </TextField>

          {isAdmin && (
            <TextField
              label="Target User ID (Admin Delegation) - Optional"
              placeholder="e.g. 2"
              value={issueForm.target_user_id}
              onChange={(e) => setIssueForm({ ...issueForm, target_user_id: e.target.value })}
              fullWidth
              size="small"
            />
          )}

          <TextField
            label="Duration (Minutes)"
            type="number"
            value={issueForm.expires_in_minutes}
            onChange={(e) => setIssueForm({ ...issueForm, expires_in_minutes: Number(e.target.value) })}
            fullWidth
            size="small"
          />

          <TextField
            label="Extra Custom Claims (JSON)"
            multiline
            rows={3}
            value={issueForm.extra_claims}
            onChange={(e) => setIssueForm({ ...issueForm, extra_claims: e.target.value })}
            fullWidth
            size="small"
            inputProps={{ style: { fontFamily: 'monospace', fontSize: 13 } }}
          />

          {issuedTokenResult && (
            <Paper sx={{ p: 2, bgcolor: '#07111D', border: '1px solid #10B981', borderRadius: 2 }}>
              <Typography variant="caption" sx={{ color: '#10B981', fontWeight: 700, display: 'block', mb: 1 }}>
                Issued RS256 Token:
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
                {issuedTokenResult}
              </Typography>
              <Button
                variant="outlined"
                size="small"
                startIcon={<CopyIcon />}
                onClick={() => handleCopy(issuedTokenResult, 'RS256 Token')}
                sx={{ mt: 1.5, color: '#10B981', borderColor: '#10B981' }}
              >
                Copy Token
              </Button>
            </Paper>
          )}
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button onClick={() => setIssueTokenModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Close
          </Button>
          <Button variant="contained" onClick={handleIssueToken} disabled={issueTokenMutation.isPending}>
            Issue Token
          </Button>
        </DialogActions>
      </Dialog>

      {/* VERIFY TOKEN MODAL */}
      <Dialog open={verifyModalOpen} onClose={() => setVerifyModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#F8FAFC' }}>Verify & Decode RS256 Token</DialogTitle>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="body2" sx={{ color: '#94A3B8', mt: 1 }}>
            Extracts the Key ID (kid) from the JWT header and validates the cryptographic signature using the public key in PostgreSQL.
          </Typography>

          <TextField
            label="Paste RS256 Token String or Scanned QR Text"
            multiline
            rows={4}
            value={verifyTokenInput}
            onChange={(e) => setVerifyTokenInput(e.target.value)}
            fullWidth
            placeholder="eyJhbGciOiJSUzI1NiIs..."
            inputProps={{ style: { fontFamily: 'monospace', fontSize: 13 } }}
          />

          <Button
            variant="contained"
            onClick={() => handleVerifyToken(verifyTokenInput)}
            disabled={!verifyTokenInput.trim() || verifyTokenMutation.isPending}
            sx={{ bgcolor: '#38BDF8', color: '#07111D', fontWeight: 700 }}
          >
            {verifyTokenMutation.isPending ? <CircularProgress size={20} /> : 'Verify Signature & Claims'}
          </Button>

          {verifyResult && (
            <Paper sx={{ p: 2, bgcolor: '#07111D', border: `1px solid ${verifyResult.valid ? '#10B981' : '#EF4444'}`, borderRadius: 2 }}>
              <Typography
                variant="subtitle2"
                sx={{ color: verifyResult.valid ? '#10B981' : '#EF4444', fontWeight: 700, mb: 1 }}
              >
                {verifyResult.valid ? 'VALID CRYPTOGRAPHIC SIGNATURE' : 'SIGNATURE VERIFICATION FAILED'}
              </Typography>
              {verifyResult.kid && (
                <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block', mb: 1 }}>
                  Verified with Key ID: <strong>{verifyResult.kid}</strong>
                </Typography>
              )}
              {verifyResult.payload && (
                <Typography
                  component="pre"
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: '#A7F3D0',
                    bgcolor: '#030712',
                    p: 1.5,
                    borderRadius: 1,
                    m: 0,
                  }}
                >
                  {JSON.stringify(verifyResult.payload, null, 2)}
                </Typography>
              )}
              {verifyResult.message && (
                <Typography variant="body2" sx={{ color: '#FCA5A5', mt: 1 }}>
                  {verifyResult.message}
                </Typography>
              )}
            </Paper>
          )}
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button onClick={() => setVerifyModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* PRODUCT TAG QR MODAL WITH GENERATE & VERIFY TABS */}
      <Dialog open={tagModalOpen} onClose={() => setTagModalOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#F8FAFC', pb: 1 }}>
          Product Tag QR Engine (RS256 Signed)
        </DialogTitle>
        <Box sx={{ borderBottom: 1, borderColor: '#1E293B', bgcolor: '#0B132B', px: 3 }}>
          <Tabs value={tagTab} onChange={(_, val) => setTagTab(val)}>
            <Tab label="Generate Product Tag QR" />
            <Tab label="Verify Tag / Scan QR Code" />
          </Tabs>
        </Box>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 3 }}>
          {tagTab === 0 && (
            <Stack spacing={2.5}>
              <Typography variant="body2" sx={{ color: '#94A3B8' }}>
                Signs arbitrary inventory attributes with RSA and dynamically generates a fitted QR code image.
              </Typography>

              <TextField
                select
                label="Signing Cryptographic Key (kid / key_id)"
                value={tagForm.key_id}
                onChange={(e) => setTagForm({ ...tagForm, key_id: e.target.value })}
                fullWidth
                size="small"
                helperText="Select which valid RSA key signs this product tag (default uses latest active key)"
              >
                <MenuItem value="">
                  <em>Latest Active Key (Auto-resolved)</em>
                </MenuItem>
                {keys.map((k) => (
                  <MenuItem key={k.id} value={k.id}>
                    🔑 {k.name} (kid: {k.kid}) — {k.status.toUpperCase()}
                  </MenuItem>
                ))}
              </TextField>

              <TextField
                label="SKU / Item Code"
                value={tagForm.sku}
                onChange={(e) => setTagForm({ ...tagForm, sku: e.target.value })}
                fullWidth
                size="small"
              />
              <TextField
                label="Batch Number"
                value={tagForm.batch}
                onChange={(e) => setTagForm({ ...tagForm, batch: e.target.value })}
                fullWidth
                size="small"
              />
              <TextField
                label="Warehouse ID"
                value={tagForm.warehouse}
                onChange={(e) => setTagForm({ ...tagForm, warehouse: e.target.value })}
                fullWidth
                size="small"
              />

              <Stack direction="row" spacing={2}>
                <TextField
                  type="number"
                  label="Expiration Duration"
                  value={tagForm.duration}
                  onChange={(e) => setTagForm({ ...tagForm, duration: Number(e.target.value) })}
                  sx={{ width: '50%' }}
                  size="small"
                />
                <FormControl sx={{ width: '50%' }} size="small">
                  <InputLabel>Unit</InputLabel>
                  <Select
                    value={tagForm.unit}
                    label="Unit"
                    onChange={(e) => setTagForm({ ...tagForm, unit: e.target.value as any })}
                  >
                    <MenuItem value="hours">Hours</MenuItem>
                    <MenuItem value="days">Days</MenuItem>
                    <MenuItem value="weeks">Weeks</MenuItem>
                    <MenuItem value="months">Months</MenuItem>
                  </Select>
                </FormControl>
              </Stack>

              <Button
                variant="contained"
                onClick={handleGenerateTag}
                disabled={generateTagMutation.isPending}
                sx={{ bgcolor: '#FACC15', color: '#0F172A', fontWeight: 700, '&:hover': { bgcolor: '#EAB308' } }}
              >
                {generateTagMutation.isPending ? <CircularProgress size={20} /> : 'Generate Scannable Tag QR'}
              </Button>

              {generateTagMutation.data && (
                <Box
                  sx={{
                    p: 3,
                    bgcolor: '#07111D',
                    borderRadius: 2,
                    border: '1px solid rgba(250, 204, 21, 0.3)',
                    display: 'flex',
                    flexDirection: { xs: 'column', sm: 'row' },
                    alignItems: 'center',
                    gap: 3,
                    mt: 2,
                  }}
                >
                  <Box
                    component="img"
                    src={generateTagMutation.data.qr_code_base64}
                    alt="Product Tag QR"
                    sx={{
                      width: 200,
                      height: 200,
                      bgcolor: '#fff',
                      p: 1.5,
                      borderRadius: 2,
                      boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
                    }}
                  />
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="subtitle2" fontWeight={700} sx={{ color: '#FACC15' }}>
                      TAG QR GENERATED SUCCESSFULLY
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block', mt: 0.5 }}>
                      Signed with Key ID: <strong>{generateTagMutation.data.kid}</strong>
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block' }}>
                      Expires at: {new Date(generateTagMutation.data.expires_at).toLocaleString()}
                    </Typography>

                    <Stack direction="row" spacing={1.5} sx={{ mt: 2 }}>
                      <Button
                        size="small"
                        variant="contained"
                        startIcon={<DownloadIcon />}
                        onClick={() =>
                          handleDownloadQR(
                            generateTagMutation.data!.qr_code_base64,
                            `tag_${generateTagMutation.data!.kid}.png`
                          )
                        }
                        sx={{ bgcolor: '#38BDF8', color: '#07111D', fontWeight: 700 }}
                      >
                        Download PNG
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<CopyIcon />}
                        onClick={() => handleCopy(generateTagMutation.data?.token || '', 'Signed JWT Token')}
                        sx={{ color: '#FACC15', borderColor: 'rgba(250, 204, 21, 0.4)' }}
                      >
                        Copy Token
                      </Button>
                    </Stack>
                  </Box>
                </Box>
              )}
            </Stack>
          )}

          {tagTab === 1 && (
            <Stack spacing={2.5}>
              <Typography variant="body2" sx={{ color: '#94A3B8' }}>
                Paste the token scanned from a physical product tag QR code to inspect payload attributes and verify its RSA signature.
              </Typography>

              <TextField
                label="Paste Scanned QR Code Token"
                multiline
                rows={4}
                value={tagVerifyInput}
                onChange={(e) => setTagVerifyInput(e.target.value)}
                fullWidth
                placeholder="eyJhbGciOiJSUzI1Ni..."
                inputProps={{ style: { fontFamily: 'monospace', fontSize: 13 } }}
              />

              <Button
                variant="contained"
                onClick={handleVerifyTag}
                disabled={!tagVerifyInput.trim() || verifyTokenMutation.isPending}
                sx={{ bgcolor: '#38BDF8', color: '#07111D', fontWeight: 700 }}
              >
                {verifyTokenMutation.isPending ? <CircularProgress size={20} /> : 'Verify Scanned Tag'}
              </Button>

              {tagVerifyResult && (
                <Paper
                  sx={{
                    p: 2.5,
                    bgcolor: '#07111D',
                    border: `1px solid ${tagVerifyResult.valid ? '#10B981' : '#EF4444'}`,
                    borderRadius: 2,
                  }}
                >
                  <Typography
                    variant="subtitle2"
                    sx={{ color: tagVerifyResult.valid ? '#10B981' : '#EF4444', fontWeight: 700, mb: 1 }}
                  >
                    {tagVerifyResult.valid ? 'VALID PRODUCT TAG' : 'INVALID TAG SIGNATURE'}
                  </Typography>
                  {tagVerifyResult.payload && (
                    <Typography
                      component="pre"
                      sx={{
                        fontFamily: 'monospace',
                        fontSize: 12,
                        color: '#A7F3D0',
                        bgcolor: '#030712',
                        p: 1.5,
                        borderRadius: 1,
                        m: 0,
                      }}
                    >
                      {JSON.stringify(tagVerifyResult.payload, null, 2)}
                    </Typography>
                  )}
                  {tagVerifyResult.message && (
                    <Typography variant="body2" sx={{ color: '#FCA5A5', mt: 1 }}>
                      {tagVerifyResult.message}
                    </Typography>
                  )}
                </Paper>
              )}
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button onClick={() => setTagModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default KeysPage;
