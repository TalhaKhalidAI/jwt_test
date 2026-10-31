// src/pages/Shifts/index.tsx
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
  Paper,
  Stack,
  Switch,
  Tabs, Alert,
  Tab,
} from '@mui/material';
import {
  PlayArrowRounded as StartIcon,
  StopRounded as StopIcon,
  AutorenewRounded as ReissueIcon,
  ContentCopyRounded as CopyIcon,
  QrCode2Rounded as QrCodeIcon,
  AccessTimeFilledRounded as ShiftIcon,
  DownloadRounded as DownloadIcon,
} from '@mui/icons-material';
import QRCode from 'qrcode';
import {
  useActiveShiftQuery,
  useShiftsQuery,
  useStartShiftMutation,
  useReissueActiveShiftMutation,
  useCheckoutShiftMutation,
} from './query';
import type { StartShiftResponse, ReissueShiftResponse } from './types';
import { ToastMsgs } from '../../api/toastUtils';
import { useAuthStore } from '../../store/authStore';

export function ShiftsPage() {
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.role === 'admin' || user?.user_role === 'admin';
  const canCreateShift = isAdmin || Boolean(user?.permissions?.['shifts.create']);

  const { data: activeShift, isLoading: isLoadingActive } = useActiveShiftQuery();
  const { data: shiftsData, isLoading: isLoadingShifts } = useShiftsQuery();

  const startShiftMutation = useStartShiftMutation();
  const reissueMutation = useReissueActiveShiftMutation();
  const checkoutMutation = useCheckoutShiftMutation();

  // Modals state
  const [startModalOpen, setStartModalOpen] = useState(false);
  const [reissueModalOpen, setReissueModalOpen] = useState(false);
  const [tokenModalOpen, setTokenModalOpen] = useState(false);
  const [tokenResult, setTokenResult] = useState<StartShiftResponse | ReissueShiftResponse | null>(null);
  const [qrCodeDataUrl, setQrCodeDataUrl] = useState<string | null>(null);
  const [tokenModalTab, setTokenModalTab] = useState<number>(0);

  // Start Form
  const [startForm, setStartForm] = useState({
    duration_hours: 8,
    device_id: 'SCANNER-MOBILE-01',
    include_rules: true,
    target_user_id: '',
  });

  // Reissue Form
  const [reissueForm, setReissueForm] = useState({
    include_rules: true,
    target_user_id: '',
  });

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    ToastMsgs.info(`${label} copied to clipboard!`);
  };

  const generateQRCode = async (token: string) => {
    try {
      const url = await QRCode.toDataURL(token, {
        width: 280,
        margin: 2,
        color: { dark: '#000000', light: '#FFFFFF' },
      });
      setQrCodeDataUrl(url);
    } catch (err) {
      console.error('Failed to render shift QR', err);
    }
  };

  const handleStartSubmit = async () => {
    const res = await startShiftMutation.mutateAsync({
      payload: {
        duration_hours: startForm.duration_hours,
        device_id: startForm.device_id,
        include_rules: startForm.include_rules,
        target_user_id: startForm.target_user_id ? Number(startForm.target_user_id) : undefined,
      },
      qrOnly: false,
    });
    setStartModalOpen(false);
    setTokenResult(res);
    setTokenModalTab(0);
    if (res.shift_token) {
      await generateQRCode(res.shift_token);
    }
    setTokenModalOpen(true);
  };

  const handleReissueSubmit = async () => {
    const res = await reissueMutation.mutateAsync({
      includeRules: reissueForm.include_rules,
      qrOnly: false,
      targetUserId: reissueForm.target_user_id ? Number(reissueForm.target_user_id) : undefined,
    });
    setReissueModalOpen(false);
    setTokenResult(res);
    setTokenModalTab(0);
    if (res.shift_token) {
      await generateQRCode(res.shift_token);
    }
    setTokenModalOpen(true);
  };

  const handleCheckout = async (shiftId?: string) => {
    await checkoutMutation.mutateAsync(shiftId);
  };

  const handleDownloadQR = () => {
    if (!qrCodeDataUrl) return;
    const a = document.createElement('a');
    a.href = qrCodeDataUrl;
    a.download = `shift_token_${tokenResult?.shift?.id?.slice(0, 8) || 'active'}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const shifts = shiftsData?.items || [];
  const hasActiveShift = Boolean(activeShift && activeShift.status === 'active');

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
            <ShiftIcon sx={{ color: '#FACC15', fontSize: 36 }} />
            Work Shifts & Scanner Sessions
          </Typography>
          <Typography variant="body2" sx={{ color: '#94A3B8', mt: 0.5 }}>
            Manage active warehouse shifts, issue scoped RS256 shift tokens, and embed offline rules for Android scanners.
          </Typography>
        </Box>

        <Stack direction="row" spacing={1.5} flexWrap="wrap">
          {hasActiveShift ? (
            <>
              <Button
                variant="outlined"
                startIcon={<ReissueIcon />}
                onClick={() => setReissueModalOpen(true)}
                disabled={reissueMutation.isPending}
                sx={{
                  borderColor: 'rgba(234, 179, 8, 0.4)',
                  color: '#FACC15',
                  '&:hover': { borderColor: '#FACC15', bgcolor: 'rgba(234, 179, 8, 0.1)' },
                }}
              >
                Reissue Token (QR & Raw)
              </Button>
              <Button
                variant="contained"
                color="error"
                startIcon={<StopIcon />}
                onClick={() => handleCheckout(activeShift?.id)}
                disabled={checkoutMutation.isPending}
              >
                Checkout & End Shift
              </Button>
            </>
          ) : (
            <>
              {isAdmin && (
                <Button
                  variant="outlined"
                  startIcon={<ReissueIcon />}
                  onClick={() => setReissueModalOpen(true)}
                  sx={{ borderColor: '#334155', color: '#FACC15' }}
                >
                  Admin Reissue Worker Shift
                </Button>
              )}
              {canCreateShift && (
                <Button
                  variant="contained"
                  startIcon={<StartIcon />}
                  onClick={() => setStartModalOpen(true)}
                  sx={{ bgcolor: '#10B981', '&:hover': { bgcolor: '#059669' } }}
                >
                  Start New Shift
                </Button>
              )}
            </>
          )}
        </Stack>
      </Box>

      {/* Active Shift Card */}
      {isLoadingActive ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : hasActiveShift ? (
        <Card
          sx={{
            mb: 4,
            bgcolor: '#0B132B',
            border: '1px solid rgba(250, 204, 21, 0.4)',
            borderRadius: 3,
            boxShadow: '0 8px 32px rgba(250, 204, 21, 0.08)',
          }}
        >
          <CardContent sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    bgcolor: '#10B981',
                    boxShadow: '0 0 12px #10B981',
                  }}
                />
                <Typography variant="h6" fontWeight={700} sx={{ color: '#F8FAFC' }}>
                  CURRENT ACTIVE SHIFT
                </Typography>
                <Chip label="ACTIVE SESSION" color="success" size="small" sx={{ fontWeight: 700 }} />
              </Box>

              <Typography variant="caption" sx={{ color: '#94A3B8', fontFamily: 'monospace' }}>
                Shift ID: {activeShift?.id}
              </Typography>
            </Box>

            <Paper sx={{ p: 2, bgcolor: '#07111D', border: '1px solid #1E293B', borderRadius: 2 }}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={3} justifyContent="space-between">
                <Box>
                  <Typography variant="caption" sx={{ color: '#64748B' }}>
                    Operator
                  </Typography>
                  <Typography variant="body2" fontWeight={600} sx={{ color: '#F8FAFC' }}>
                    {user?.name || user?.email} (ID #{activeShift?.user_id})
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" sx={{ color: '#64748B' }}>
                    Scanner Device ID
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#38BDF8', fontFamily: 'monospace' }}>
                    {activeShift?.device_id || 'DEFAULT_SCANNER'}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" sx={{ color: '#64748B' }}>
                    Signing Key
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#A7F3D0', fontFamily: 'monospace' }}>
                    {activeShift?.key_id ? `${activeShift.key_id.slice(0, 8)}...` : 'Active Default'}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" sx={{ color: '#64748B' }}>
                    Session Started
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#F8FAFC' }}>
                    {activeShift?.started_at ? new Date(activeShift.started_at).toLocaleTimeString() : 'N/A'}
                  </Typography>
                </Box>
              </Stack>
            </Paper>
          </CardContent>
        </Card>
      ) : (
        <Alert severity="info" sx={{ mb: 4, bgcolor: '#0B132B', border: '1px solid #1E293B', color: '#94A3B8' }}>
          No active work shift currently open for your account. Start a new shift to generate an authorization QR token for your scanner.
        </Alert>
      )}

      {/* Shifts History Table */}
      <Card sx={{ bgcolor: '#0B132B', border: '1px solid #1E293B', borderRadius: 3 }}>
        <CardContent sx={{ p: 0 }}>
          <TableContainer>
            <Table>
              <TableHead sx={{ bgcolor: '#07111D' }}>
                <TableRow>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Shift / User</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Device ID</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Key ID</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Status</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Timing</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600, textAlign: 'right' }}>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {isLoadingShifts ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ py: 6 }}>
                      <CircularProgress color="primary" />
                    </TableCell>
                  </TableRow>
                ) : shifts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ py: 6, color: '#94A3B8' }}>
                      No shift records found.
                    </TableCell>
                  </TableRow>
                ) : (
                  shifts.map((s) => {
                    const isActive = s.status === 'active';
                    return (
                      <TableRow key={s.id} sx={{ '&:hover': { bgcolor: '#0D1B3E' } }}>
                        <TableCell>
                          <Typography variant="body2" fontWeight={600} sx={{ color: '#F8FAFC' }}>
                            User #{s.user_id}
                          </Typography>
                          <Typography variant="caption" sx={{ color: '#64748B', fontFamily: 'monospace' }}>
                            {s.id.slice(0, 8)}...
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" sx={{ color: '#E2E8F0', fontFamily: 'monospace' }}>
                            {s.device_id || 'DEFAULT'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption" sx={{ color: '#38BDF8', fontFamily: 'monospace' }}>
                            {s.key_id ? s.key_id.slice(0, 10) : 'N/A'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={s.status.toUpperCase()}
                            size="small"
                            color={isActive ? 'success' : 'default'}
                            sx={{ fontWeight: 700, fontSize: 11 }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block' }}>
                            Start: {s.started_at ? new Date(s.started_at).toLocaleTimeString() : 'N/A'}
                          </Typography>
                          <Typography variant="caption" sx={{ color: '#64748B', display: 'block' }}>
                            End: {s.ended_at ? new Date(s.ended_at).toLocaleTimeString() : 'In Progress'}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          {isActive && (
                            <Button
                              size="small"
                              variant="outlined"
                              color="error"
                              onClick={() => handleCheckout(s.id)}
                            >
                              Checkout
                            </Button>
                          )}
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

      {/* START SHIFT MODAL */}
      <Dialog open={startModalOpen} onClose={() => setStartModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#F8FAFC' }}>Start New Work Shift</DialogTitle>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="body2" sx={{ color: '#94A3B8', mt: 1 }}>
            Initiates an authenticated session and issues a scoped <code>shift_token</code> JWT scannable from the screen.
          </Typography>

          <FormControl fullWidth size="small">
            <InputLabel>Shift Duration</InputLabel>
            <Select
              value={startForm.duration_hours}
              label="Shift Duration"
              onChange={(e) => setStartForm({ ...startForm, duration_hours: Number(e.target.value) })}
            >
              <MenuItem value={4}>4 Hours</MenuItem>
              <MenuItem value={8}>8 Hours (Standard)</MenuItem>
              <MenuItem value={12}>12 Hours</MenuItem>
              <MenuItem value={24}>24 Hours</MenuItem>
            </Select>
          </FormControl>

          <TextField
            label="Scanner Device ID"
            value={startForm.device_id}
            onChange={(e) => setStartForm({ ...startForm, device_id: e.target.value })}
            fullWidth
            size="small"
          />

          {isAdmin && (
            <TextField
              label="Target User ID (Admin Delegation) - Optional"
              placeholder="e.g. 2"
              value={startForm.target_user_id}
              onChange={(e) => setStartForm({ ...startForm, target_user_id: e.target.value })}
              fullWidth
              size="small"
            />
          )}

          <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mt: 1 }}>
            <Switch
              checked={startForm.include_rules}
              onChange={(e) => setStartForm({ ...startForm, include_rules: e.target.checked })}
            />
            <Box>
              <Typography variant="body2" sx={{ color: '#F8FAFC', fontWeight: 600 }}>
                Embed Active Inventory Rules
              </Typography>
              <Typography variant="caption" sx={{ color: '#94A3B8' }}>
                Enables mobile scanner to validate products offline without constant Wi-Fi connectivity.
              </Typography>
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button onClick={() => setStartModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleStartSubmit}
            disabled={startShiftMutation.isPending}
            sx={{ bgcolor: '#10B981', '&:hover': { bgcolor: '#059669' } }}
          >
            Start Shift & Render QR
          </Button>
        </DialogActions>
      </Dialog>

      {/* REISSUE SHIFT MODAL */}
      <Dialog open={reissueModalOpen} onClose={() => setReissueModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#F8FAFC' }}>
          Reissue Active Shift Token (QR & Raw)
        </DialogTitle>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant="body2" sx={{ color: '#94A3B8', mt: 1 }}>
            Re-mints a fresh <code>shift_token</code> JWT for your currently active session, available both as a scannable on-screen QR code and raw token string.
          </Typography>

          {isAdmin && (
            <TextField
              label="Target User ID (Admin Delegation) - Optional"
              placeholder="Leave empty to reissue own token"
              value={reissueForm.target_user_id}
              onChange={(e) => setReissueForm({ ...reissueForm, target_user_id: e.target.value })}
              fullWidth
              size="small"
            />
          )}

          <Stack direction="row" alignItems="center" spacing={1.5}>
            <Switch
              checked={reissueForm.include_rules}
              onChange={(e) => setReissueForm({ ...reissueForm, include_rules: e.target.checked })}
            />
            <Box>
              <Typography variant="body2" sx={{ color: '#F8FAFC', fontWeight: 600 }}>
                Embed Active Inventory Rules
              </Typography>
              <Typography variant="caption" sx={{ color: '#94A3B8' }}>
                Embed current rules inside token payload for offline scanner verification.
              </Typography>
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button onClick={() => setReissueModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleReissueSubmit}
            disabled={reissueMutation.isPending}
            sx={{ bgcolor: '#FACC15', color: '#0F172A', fontWeight: 700, '&:hover': { bgcolor: '#EAB308' } }}
          >
            Reissue Token
          </Button>
        </DialogActions>
      </Dialog>

      {/* SHIFT TOKEN MODAL: SCANNABLE QR & RAW FORM */}
      <Dialog open={tokenModalOpen} onClose={() => setTokenModalOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ bgcolor: '#0B132B', color: '#F8FAFC', pb: 1, display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <QrCodeIcon sx={{ color: '#FACC15' }} />
          Shift Authorization Credential
        </DialogTitle>
        <Box sx={{ borderBottom: 1, borderColor: '#1E293B', bgcolor: '#0B132B', px: 3 }}>
          <Tabs value={tokenModalTab} onChange={(_, val) => setTokenModalTab(val)}>
            <Tab label="Scannable QR Code" />
            <Tab label="Raw JWT Token String" />
          </Tabs>
        </Box>
        <DialogContent sx={{ bgcolor: '#0B132B', pt: 3 }}>
          {tokenModalTab === 0 && (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2.5 }}>
              <Typography variant="body2" sx={{ color: '#94A3B8', textAlign: 'center' }}>
                Point the Android scanner camera or mobile barcode reader directly at this QR code to login.
              </Typography>

              {qrCodeDataUrl ? (
                <Paper sx={{ p: 2, bgcolor: '#FFFFFF', borderRadius: 3, boxShadow: '0 8px 30px rgba(0,0,0,0.6)' }}>
                  <img
                    src={qrCodeDataUrl}
                    alt="Shift Token QR"
                    style={{ display: 'block', width: 240, height: 240 }}
                  />
                </Paper>
              ) : (
                <CircularProgress />
              )}

              <Stack direction="row" spacing={2}>
                <Button
                  variant="contained"
                  startIcon={<DownloadIcon />}
                  onClick={handleDownloadQR}
                  sx={{ bgcolor: '#38BDF8', color: '#07111D', fontWeight: 700 }}
                >
                  Download QR Image (PNG)
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<CopyIcon />}
                  onClick={() => handleCopy(tokenResult?.shift_token || '', 'Shift Token')}
                  sx={{ color: '#FACC15', borderColor: '#FACC15' }}
                >
                  Copy Token String
                </Button>
              </Stack>
            </Box>
          )}

          {tokenModalTab === 1 && (
            <Stack spacing={2}>
              <Typography variant="body2" sx={{ color: '#94A3B8' }}>
                Raw RS256 Shift JWT token string. Can be pasted into headers or configuration payloads:
              </Typography>

              <Paper
                sx={{
                  p: 2,
                  bgcolor: '#07111D',
                  border: '1px solid #1E293B',
                  borderRadius: 2,
                  maxHeight: 220,
                  overflowY: 'auto',
                }}
              >
                <Typography
                  variant="body2"
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: 12,
                    wordBreak: 'break-all',
                    color: '#A7F3D0',
                    m: 0,
                  }}
                >
                  {tokenResult?.shift_token}
                </Typography>
              </Paper>

              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="caption" sx={{ color: '#64748B' }}>
                  Shift ID: {tokenResult?.shift?.id}
                </Typography>
                <Button
                  variant="outlined"
                  startIcon={<CopyIcon />}
                  onClick={() => handleCopy(tokenResult?.shift_token || '', 'Raw JWT Token')}
                  sx={{ color: '#38BDF8', borderColor: '#38BDF8' }}
                >
                  Copy Raw Token
                </Button>
              </Box>
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ bgcolor: '#0B132B', p: 2 }}>
          <Button onClick={() => setTokenModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default ShiftsPage;
