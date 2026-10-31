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
  CircularProgress,
  Tooltip,
  Paper,
  Stack,
  Alert,
} from '@mui/material';
import {
  QrCodeScannerRounded as ScansIcon,
  CheckCircleRounded as CheckIcon,
  CancelRounded as CancelIcon,
  VisibilityRounded as VisibilityIcon,
  VerifiedUserRounded as VerifyIcon,
} from '@mui/icons-material';
import { useScansQuery, useVerifyTokenDirectMutation } from './query';
import type { ScanRecord } from './types';
import { ToastMsgs } from '../../api/toastUtils';

export function ScansPage() {
  const { data: scansData, isLoading } = useScansQuery();
  const verifyTokenMutation = useVerifyTokenDirectMutation();

  const [inspectModalOpen, setInspectModalOpen] = useState(false);
  const [selectedScan, setSelectedScan] = useState<ScanRecord | null>(null);

  const [verifyModalOpen, setVerifyModalOpen] = useState(false);
  const [tokenToVerify, setTokenToVerify] = useState('');

  const handleVerifySubmit = async () => {
    if (!tokenToVerify.trim()) {
      ToastMsgs.error('Please paste a JWT token');
      return;
    }
    await verifyTokenMutation.mutateAsync(tokenToVerify.trim());
  };

  const scans = scansData?.items || [];
  const validCount = scans.filter((s) => s.status === 'valid').length;
  const invalidCount = scans.filter((s) => s.status !== 'valid').length;

  return (
    <Box sx={{ maxWidth: 1400, mx: 'auto' }}>
      {/* Top Banner */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', md: 'row' },
          justifyContent: 'space-between',
          alignItems: { xs: 'flex-start', md: 'center' },
          gap: 2,
          mb: 3,
        }}
      >
        <Box>
          <Typography variant="h5" fontWeight={800} sx={{ letterSpacing: -0.5 }}>
            Scan Audits & Telemetry
          </Typography>
          <Typography variant="body2" sx={{ color: '#94A3B8', mt: 0.5 }}>
            Real-time audit log of product scans collected online and synchronized from offline mobile scanners.
          </Typography>
        </Box>

        <Stack direction="row" spacing={1.5}>
          <Button
            variant="contained"
            startIcon={<VerifyIcon />}
            onClick={() => setVerifyModalOpen(true)}
            sx={{ bgcolor: '#2563EB', '&:hover': { bgcolor: '#1D4ED8' } }}
          >
            Verify JWT Signature
          </Button>
        </Stack>
      </Box>

      {/* Metrics Row */}
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 3 }}>
        <Paper
          sx={{
            p: 2,
            flex: 1,
            bgcolor: '#0B132B',
            borderRadius: 2,
            border: '1px solid rgba(255, 255, 255, 0.08)',
          }}
        >
          <Typography variant="caption" sx={{ color: '#94A3B8', fontWeight: 600 }}>
            TOTAL INGESTED SCANS
          </Typography>
          <Typography variant="h4" fontWeight={800} sx={{ color: '#F8FAFC', mt: 0.5 }}>
            {scans.length}
          </Typography>
        </Paper>

        <Paper
          sx={{
            p: 2,
            flex: 1,
            bgcolor: '#0B132B',
            borderRadius: 2,
            border: '1px solid rgba(16, 185, 129, 0.3)',
          }}
        >
          <Typography variant="caption" sx={{ color: '#34D399', fontWeight: 600 }}>
            VALID VERIFICATIONS
          </Typography>
          <Typography variant="h4" fontWeight={800} sx={{ color: '#34D399', mt: 0.5 }}>
            {validCount}
          </Typography>
        </Paper>

        <Paper
          sx={{
            p: 2,
            flex: 1,
            bgcolor: '#0B132B',
            borderRadius: 2,
            border: '1px solid rgba(239, 68, 68, 0.3)',
          }}
        >
          <Typography variant="caption" sx={{ color: '#F87171', fontWeight: 600 }}>
            POLICY VIOLATIONS / INVALID
          </Typography>
          <Typography variant="h4" fontWeight={800} sx={{ color: '#F87171', mt: 0.5 }}>
            {invalidCount}
          </Typography>
        </Paper>
      </Stack>

      {/* Scans Table */}
      <Card
        sx={{
          bgcolor: '#0B132B',
          borderRadius: 3,
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
        }}
      >
        <CardContent sx={{ p: 0 }}>
          <TableContainer component={Paper} sx={{ bgcolor: 'transparent', boxShadow: 'none' }}>
            <Table>
              <TableHead sx={{ bgcolor: 'rgba(255, 255, 255, 0.03)' }}>
                <TableRow>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>VERIFICATION</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>SCAN ID</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>DETECTED SKU / PAYLOAD</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>SHIFT BINDING</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>TIMESTAMPS</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }} align="right">
                    DETAILS
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ py: 6 }}>
                      <CircularProgress size={32} sx={{ color: '#3B82F6' }} />
                      <Typography variant="body2" sx={{ color: '#94A3B8', mt: 1.5 }}>
                        Loading scan history telemetry...
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : scans.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ py: 6 }}>
                      <ScansIcon sx={{ fontSize: 44, color: '#475569', mb: 1 }} />
                      <Typography variant="subtitle1" fontWeight={600} sx={{ color: '#94A3B8' }}>
                        No scans logged yet
                      </Typography>
                      <Typography variant="body2" sx={{ color: '#64748B' }}>
                        Scans made by mobile devices with active shift tokens will stream here automatically.
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  scans.map((s) => {
                    const isValid = s.status === 'valid';
                    const sku =
                      s.jwt_scanned?.sku ||
                      s.jwt_scanned?.product_id ||
                      s.jwt_scanned?.batch_no ||
                      'TAG-PAYLOAD';

                    return (
                      <TableRow
                        key={s.id}
                        sx={{
                          borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                          '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.02)' },
                        }}
                      >
                        <TableCell>
                          <Chip
                            icon={isValid ? <CheckIcon /> : <CancelIcon />}
                            size="small"
                            label={s.status.toUpperCase()}
                            sx={{
                              fontWeight: 700,
                              fontSize: '0.68rem',
                              bgcolor: isValid ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                              color: isValid ? '#34D399' : '#F87171',
                              border: `1px solid ${isValid ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                              '& .MuiChip-icon': {
                                color: isValid ? '#34D399' : '#F87171',
                              },
                            }}
                          />
                        </TableCell>

                        <TableCell>
                          <Typography variant="body2" fontWeight={700} sx={{ color: '#F8FAFC', fontFamily: 'monospace' }}>
                            #{s.id}
                          </Typography>
                        </TableCell>

                        <TableCell>
                          <Typography variant="body2" fontWeight={600} sx={{ color: '#E2E8F0' }}>
                            {String(sku)}
                          </Typography>
                          {s.reason && (
                            <Typography variant="caption" sx={{ color: '#F87171', display: 'block' }}>
                              Violation: {s.reason}
                            </Typography>
                          )}
                        </TableCell>

                        <TableCell>
                          <Typography variant="caption" sx={{ color: '#60A5FA', fontFamily: 'monospace' }}>
                            {s.shift_id.slice(0, 12)}...
                          </Typography>
                        </TableCell>

                        <TableCell>
                          <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block' }}>
                            Captured: {s.scanned_at ? new Date(s.scanned_at).toLocaleString() : 'N/A'}
                          </Typography>
                          {s.synced_at && (
                            <Typography variant="caption" sx={{ color: '#64748B', display: 'block' }}>
                              Synced: {new Date(s.synced_at).toLocaleTimeString()}
                            </Typography>
                          )}
                        </TableCell>

                        <TableCell align="right">
                          <Tooltip title="Inspect Decoded Claims">
                            <IconButton
                              size="small"
                              onClick={() => {
                                setSelectedScan(s);
                                setInspectModalOpen(true);
                              }}
                              sx={{ color: '#60A5FA' }}
                            >
                              <VisibilityIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
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

      {/* Modal: Inspect Decoded Claims */}
      <Dialog
        open={inspectModalOpen}
        onClose={() => setInspectModalOpen(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: { bgcolor: '#0F172A', color: '#F8FAFC', border: '1px solid rgba(255, 255, 255, 0.1)' },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700 }}>Scan Record #{selectedScan?.id} Claims</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: '#94A3B8', mb: 2 }}>
            Attributes payload decoded from scanned item during shift:
          </Typography>

          <Paper
            sx={{
              p: 2,
              bgcolor: '#07111D',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 2,
              maxHeight: 400,
              overflowY: 'auto',
            }}
          >
            <Typography
              component="pre"
              sx={{ fontFamily: 'monospace', fontSize: '0.85rem', color: '#38BDF8', m: 0 }}
            >
              {JSON.stringify(selectedScan?.jwt_scanned || {}, null, 2)}
            </Typography>
          </Paper>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setInspectModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Modal: Verify JWT Signature */}
      <Dialog
        open={verifyModalOpen}
        onClose={() => setVerifyModalOpen(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: { bgcolor: '#0F172A', color: '#F8FAFC', border: '1px solid rgba(255, 255, 255, 0.1)' },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700 }}>Verify RS256 Token Signature</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: '#94A3B8', mb: 2 }}>
            Verifies signature using the database public key matching the token's unverified <code>kid</code> header.
          </Typography>

          <TextField
            fullWidth
            multiline
            rows={4}
            label="Raw JWT String (ey...)"
            placeholder="eyJhbGciOiJSUzI1NiIsImtpZCI6..."
            value={tokenToVerify}
            onChange={(e) => setTokenToVerify(e.target.value)}
            sx={{
              mb: 2,
              '& .MuiInputBase-input': { fontFamily: 'monospace', fontSize: '0.85rem' },
            }}
          />

          <Button
            variant="contained"
            onClick={handleVerifySubmit}
            disabled={verifyTokenMutation.isPending}
            sx={{ bgcolor: '#2563EB', mb: 2 }}
          >
            {verifyTokenMutation.isPending ? <CircularProgress size={20} /> : 'Verify with RSA Engine'}
          </Button>

          {verifyTokenMutation.data && (
            <Alert severity="success" sx={{ bgcolor: 'rgba(16, 185, 129, 0.15)', color: '#34D399' }}>
              <strong>VALID RS256 SIGNATURE</strong>: Key ID:{' '}
              <code>{verifyTokenMutation.data.kid || verifyTokenMutation.data.key_id}</code>
            </Alert>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setVerifyModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default ScansPage;
