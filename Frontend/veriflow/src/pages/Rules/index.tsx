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
  Switch,
  Alert,
  MenuItem,
} from '@mui/material';
import {
  AddRounded as AddIcon,
  EditRounded as EditIcon,
  DeleteRounded as DeleteIcon,
  PlayArrowRounded as TestIcon,
  RuleRounded as RuleIcon,
  VerifiedUserRounded as PolicyIcon,
} from '@mui/icons-material';
import {
  useRulesQuery,
  useCreateRuleMutation,
  useUpdateRuleMutation,
  useToggleRuleStatusMutation,
  useDeleteRuleMutation,
  useEvaluateClaimsMutation,
  useApplicableRulesQuery,
} from './query';
import { useKeysQuery } from '../Keys/query';
import type { InventoryRule } from './types';
import { ToastMsgs } from '../../api/toastUtils';
import { useAuthStore } from '../../store/authStore';

export function RulesPage() {
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.role === 'admin' || user?.user_role === 'admin';
  const canCreateRule = isAdmin || Boolean(user?.permissions?.['inventory_rules.create']);
  const canUpdateRule = isAdmin || Boolean(user?.permissions?.['inventory_rules.update']);
  const canDeleteRule = isAdmin || Boolean(user?.permissions?.['inventory_rules.delete']);

  const { data: keysData } = useKeysQuery();
  const keys = keysData?.items || [];

  const [applicableModalOpen, setApplicableModalOpen] = useState(false);
  const [applicableKeyId, setApplicableKeyId] = useState('');
  const { data: applicableRules = [], isLoading: isLoadingApplicable } = useApplicableRulesQuery(
    applicableKeyId || undefined
  );

  const { data: rulesData, isLoading } = useRulesQuery();
  const createRuleMutation = useCreateRuleMutation();
  const updateRuleMutation = useUpdateRuleMutation();
  const toggleRuleMutation = useToggleRuleStatusMutation();
  const deleteRuleMutation = useDeleteRuleMutation();
  const evaluateMutation = useEvaluateClaimsMutation();

  // Dialog States
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<InventoryRule | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [ruleToDelete, setRuleToDelete] = useState<InventoryRule | null>(null);
  const [testDialogOpen, setTestDialogOpen] = useState(false);

  // Form State
  const [form, setForm] = useState({
    rule_name: '',
    matching_claim_key: 'warehouse_id',
    expected_value: 'WH-CENTRAL-01',
    key_id: '',
    is_active: true,
  });

  // Test Claims State
  const [testClaimsJson, setTestClaimsJson] = useState(
    JSON.stringify({ warehouse_id: 'WH-CENTRAL-01', sku: 'SKU-88', status: 'verified' }, null, 2)
  );

  const handleOpenCreate = () => {
    setEditingRule(null);
    setForm({
      rule_name: '',
      matching_claim_key: 'warehouse_id',
      expected_value: 'WH-CENTRAL-01',
      key_id: '',
      is_active: true,
    });
    setModalOpen(true);
  };

  const handleOpenEdit = (rule: InventoryRule) => {
    setEditingRule(rule);
    setForm({
      rule_name: rule.rule_name,
      matching_claim_key: rule.matching_claim_key,
      expected_value: rule.expected_value,
      key_id: rule.key_id || '',
      is_active: rule.is_active,
    });
    setModalOpen(true);
  };

  const handleSaveRule = async () => {
    if (!form.rule_name.trim() || !form.matching_claim_key.trim() || !form.expected_value.trim()) {
      ToastMsgs.error('All rule fields are required');
      return;
    }

    const payload = {
      ...form,
      key_id: form.key_id.trim() ? form.key_id.trim() : null,
    };

    if (editingRule) {
      await updateRuleMutation.mutateAsync({
        ruleId: editingRule.id,
        payload,
      });
    } else {
      await createRuleMutation.mutateAsync(payload);
    }
    setModalOpen(false);
  };

  const handleDeleteConfirm = async () => {
    if (!ruleToDelete) return;
    await deleteRuleMutation.mutateAsync(ruleToDelete.id);
    setDeleteDialogOpen(false);
    setRuleToDelete(null);
  };

  const handleRunEvaluation = async () => {
    try {
      const parsedClaims = JSON.parse(testClaimsJson);
      await evaluateMutation.mutateAsync({ claims: parsedClaims });
    } catch {
      ToastMsgs.error('Invalid JSON payload in claims test');
    }
  };

  const rules = rulesData?.items || [];

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
            Inventory Rules & Verification Policies
          </Typography>
          <Typography variant="body2" sx={{ color: '#94A3B8', mt: 0.5 }}>
            Configure matching rules for JWT claims embedded in QR product tags and shift authorizations.
          </Typography>
        </Box>

        <Stack direction="row" spacing={1.5}>
          <Button
            variant="outlined"
            startIcon={<PolicyIcon />}
            onClick={() => setApplicableModalOpen(true)}
            sx={{
              borderColor: 'rgba(56, 189, 248, 0.4)',
              color: '#38BDF8',
              '&:hover': { borderColor: '#38BDF8', bgcolor: 'rgba(56, 189, 248, 0.1)' },
            }}
          >
            Applicable Verification Rules
          </Button>

          <Button
            variant="outlined"
            startIcon={<TestIcon />}
            onClick={() => setTestDialogOpen(true)}
            sx={{
              borderColor: 'rgba(255, 255, 255, 0.15)',
              color: '#F8FAFC',
              '&:hover': { borderColor: '#3B82F6', bgcolor: 'rgba(59, 130, 246, 0.1)' },
            }}
          >
            Evaluate Claims Matrix
          </Button>

          {canCreateRule && (
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleOpenCreate}
              sx={{ bgcolor: '#2563EB', '&:hover': { bgcolor: '#1D4ED8' } }}
            >
              Add Verification Rule
            </Button>
          )}
        </Stack>
      </Box>

      {/* Rules Table */}
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
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>ENFORCEMENT</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>RULE NAME</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>TARGET CLAIM KEY</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>EXPECTED VALUE</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>SCOPE</TableCell>
                  <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }} align="right">
                    ACTIONS
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ py: 6 }}>
                      <CircularProgress size={32} sx={{ color: '#3B82F6' }} />
                      <Typography variant="body2" sx={{ color: '#94A3B8', mt: 1.5 }}>
                        Loading inventory verification rules...
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : rules.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ py: 6 }}>
                      <RuleIcon sx={{ fontSize: 44, color: '#475569', mb: 1 }} />
                      <Typography variant="subtitle1" fontWeight={600} sx={{ color: '#94A3B8' }}>
                        No inventory rules defined
                      </Typography>
                      {canCreateRule && (
                        <Button variant="outlined" startIcon={<AddIcon />} onClick={handleOpenCreate} size="small" sx={{ mt: 2 }}>
                          Add First Rule
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ) : (
                  rules.map((r) => (
                    <TableRow
                      key={r.id}
                      sx={{
                        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                        '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.02)' },
                      }}
                    >
                      <TableCell>
                        <Stack direction="row" alignItems="center" spacing={1}>
                          <Switch
                            size="small"
                            checked={r.is_active}
                            disabled={!canUpdateRule}
                            onChange={(e) =>
                              toggleRuleMutation.mutate({ ruleId: r.id, isActive: e.target.checked })
                            }
                            sx={{
                              '& .MuiSwitch-switchBase.Mui-checked': { color: '#10B981' },
                              '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                                bgcolor: '#10B981',
                              },
                            }}
                          />
                          <Chip
                            size="small"
                            label={r.is_active ? 'ACTIVE' : 'DISABLED'}
                            sx={{
                              fontWeight: 700,
                              fontSize: '0.65rem',
                              bgcolor: r.is_active ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.15)',
                              color: r.is_active ? '#34D399' : '#94A3B8',
                            }}
                          />
                        </Stack>
                      </TableCell>

                      <TableCell>
                        <Typography variant="body2" fontWeight={700} sx={{ color: '#F8FAFC' }}>
                          {r.rule_name}
                        </Typography>
                        <Typography variant="caption" sx={{ color: '#64748B' }}>
                          ID: {r.id.slice(0, 8)}...
                        </Typography>
                      </TableCell>

                      <TableCell>
                        <Chip
                          size="small"
                          label={r.matching_claim_key}
                          sx={{
                            fontFamily: 'monospace',
                            bgcolor: 'rgba(59, 130, 246, 0.15)',
                            color: '#60A5FA',
                            fontWeight: 600,
                          }}
                        />
                      </TableCell>

                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', color: '#FACC15' }}>
                          == "{r.expected_value}"
                        </Typography>
                      </TableCell>

                      <TableCell>
                        <Chip
                          size="small"
                          label={r.key_id ? `Key: ${r.key_id.slice(0, 8)}...` : 'GLOBAL (All Keys)'}
                          sx={{
                            fontSize: '0.7rem',
                            bgcolor: r.key_id ? 'rgba(147, 51, 234, 0.15)' : 'rgba(255, 255, 255, 0.06)',
                            color: r.key_id ? '#C084FC' : '#CBD5E1',
                          }}
                        />
                      </TableCell>

                      <TableCell align="right">
                        <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                          {canUpdateRule && (
                            <Tooltip title="Edit Rule">
                              <IconButton size="small" onClick={() => handleOpenEdit(r)} sx={{ color: '#60A5FA' }}>
                                <EditIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}

                          {canDeleteRule && (
                            <Tooltip title="Delete Rule">
                              <IconButton
                                size="small"
                                onClick={() => {
                                  setRuleToDelete(r);
                                  setDeleteDialogOpen(true);
                                }}
                                sx={{ color: '#EF4444' }}
                              >
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}
                        </Stack>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Modal: Create or Edit Rule */}
      <Dialog
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: { bgcolor: '#0F172A', color: '#F8FAFC', border: '1px solid rgba(255, 255, 255, 0.1)' },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700 }}>
          {editingRule ? 'Edit Verification Policy' : 'Create Verification Policy'}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: '#94A3B8', mb: 3 }}>
            Enforces policy checks when a mobile scanner inspects product tags or worker shift credentials.
          </Typography>

          <TextField
            fullWidth
            label="Rule Name"
            placeholder="e.g. Warehouse 101 Access Policy"
            value={form.rule_name}
            onChange={(e) => setForm({ ...form, rule_name: e.target.value })}
            sx={{ mb: 2 }}
          />

          <TextField
            select
            fullWidth
            label="Target Cryptographic Key"
            value={form.key_id}
            onChange={(e) => setForm({ ...form, key_id: e.target.value })}
            helperText={
              isAdmin
                ? "Select a specific key to bind this policy, or choose Global to enforce across all tokens."
                : "Select the cryptographic key you own that this policy applies to."
            }
            sx={{ mb: 2 }}
          >
            {isAdmin && (
              <MenuItem value="">
                <em>🌐 Global Verification Policy (All Keys)</em>
              </MenuItem>
            )}
            {keys.map((k) => (
              <MenuItem key={k.id} value={k.id}>
                🔑 {k.name} (kid: {k.kid}) — {k.status.toUpperCase()}
              </MenuItem>
            ))}
          </TextField>

          <TextField
            fullWidth
            label="Matching Claim Key"
            placeholder="e.g. warehouse_id, status, facility"
            value={form.matching_claim_key}
            onChange={(e) => setForm({ ...form, matching_claim_key: e.target.value })}
            helperText="The JWT attribute name extracted from the scanned QR code"
            sx={{ mb: 2 }}
          />

          <TextField
            fullWidth
            label="Expected Exact Match Value"
            placeholder="e.g. WH-CENTRAL-01"
            value={form.expected_value}
            onChange={(e) => setForm({ ...form, expected_value: e.target.value })}
            sx={{ mb: 2 }}
          />

          <Stack direction="row" alignItems="center" spacing={1}>
            <Switch
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            <Typography variant="body2">Rule is immediately active</Typography>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSaveRule}
            disabled={createRuleMutation.isPending || updateRuleMutation.isPending}
            sx={{ bgcolor: '#2563EB' }}
          >
            {createRuleMutation.isPending || updateRuleMutation.isPending ? (
              <CircularProgress size={20} />
            ) : editingRule ? (
              'Save Changes'
            ) : (
              'Create Policy'
            )}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Modal: Applicable Rules for Verification (GET /rules/applicable) */}
      <Dialog
        open={applicableModalOpen}
        onClose={() => setApplicableModalOpen(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: { bgcolor: '#0B132B', color: '#F8FAFC', border: '1px solid #1E293B', borderRadius: 3 },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700, color: '#38BDF8', display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <PolicyIcon /> Active Applicable Verification Policies
        </DialogTitle>
        <DialogContent sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2.5 }}>
          <Typography variant="body2" sx={{ color: '#94A3B8' }}>
            Inspect active policies that apply to a token verification context (Global + Key-Specific). The scan verification engine enforces these exact rules when validating claims.
          </Typography>

          <TextField
            select
            fullWidth
            label="Verification Signing Key Context (key_id)"
            value={applicableKeyId}
            onChange={(e) => setApplicableKeyId(e.target.value)}
            size="small"
            helperText="Filter applicable rules by signing key. If none selected, returns universal global rules."
          >
            <MenuItem value="">
              <em>All / Global Context Only (No specific key)</em>
            </MenuItem>
            {keys.map((k) => (
              <MenuItem key={k.id} value={k.id}>
                🔑 {k.name} (kid: {k.kid}) — {k.status.toUpperCase()}
              </MenuItem>
            ))}
          </TextField>

          {isLoadingApplicable ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress size={28} sx={{ color: '#38BDF8' }} />
            </Box>
          ) : applicableRules.length === 0 ? (
            <Paper sx={{ p: 3, bgcolor: '#07111D', border: '1px dashed #334155', textAlign: 'center', borderRadius: 2 }}>
              <Typography variant="body2" sx={{ color: '#94A3B8' }}>
                No active applicable rules found for this verification context.
              </Typography>
            </Paper>
          ) : (
            <TableContainer component={Paper} sx={{ bgcolor: '#07111D', border: '1px solid #1E293B', borderRadius: 2 }}>
              <Table size="small">
                <TableHead sx={{ bgcolor: 'rgba(255, 255, 255, 0.03)' }}>
                  <TableRow>
                    <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>POLICY NAME</TableCell>
                    <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>CLAIM KEY</TableCell>
                    <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>EXPECTED VALUE</TableCell>
                    <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>APPLICABLE SCOPE</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {applicableRules.map((ar) => (
                    <TableRow key={ar.id}>
                      <TableCell sx={{ color: '#F8FAFC', fontWeight: 600 }}>{ar.rule_name}</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={ar.matching_claim_key}
                          sx={{ fontFamily: 'monospace', bgcolor: 'rgba(59, 130, 246, 0.15)', color: '#60A5FA' }}
                        />
                      </TableCell>
                      <TableCell sx={{ color: '#FACC15', fontFamily: 'monospace' }}>== "{ar.expected_value}"</TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={ar.key_id ? `Key: ${ar.key_id.slice(0, 8)}...` : 'GLOBAL'}
                          sx={{
                            fontSize: 10,
                            bgcolor: ar.key_id ? 'rgba(147, 51, 234, 0.15)' : 'rgba(255, 255, 255, 0.06)',
                            color: ar.key_id ? '#C084FC' : '#CBD5E1',
                          }}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setApplicableModalOpen(false)} sx={{ color: '#94A3B8' }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Modal: Delete Confirmation */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        maxWidth="xs"
        PaperProps={{
          sx: { bgcolor: '#0F172A', color: '#F8FAFC', border: '1px solid rgba(255, 255, 255, 0.1)' },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700, color: '#EF4444' }}>Delete Rule?</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: '#94A3B8' }}>
            Are you sure you want to permanently remove <strong>{ruleToDelete?.rule_name}</strong>? Scanners will no longer enforce this requirement.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setDeleteDialogOpen(false)} sx={{ color: '#94A3B8' }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleDeleteConfirm}
            disabled={deleteRuleMutation.isPending}
          >
            {deleteRuleMutation.isPending ? <CircularProgress size={20} /> : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Modal: Evaluate Claims Simulator */}
      <Dialog
        open={testDialogOpen}
        onClose={() => setTestDialogOpen(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: { bgcolor: '#0F172A', color: '#F8FAFC', border: '1px solid rgba(255, 255, 255, 0.1)' },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700 }}>Evaluate Claim Set Simulator</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: '#94A3B8', mb: 2 }}>
            Simulate offline and online tag verification by passing raw decoded claims into the rule evaluator.
          </Typography>

          <TextField
            fullWidth
            multiline
            rows={5}
            label="Claims JSON Payload"
            value={testClaimsJson}
            onChange={(e) => setTestClaimsJson(e.target.value)}
            sx={{
              mb: 2,
              '& .MuiInputBase-input': { fontFamily: 'monospace', fontSize: '0.85rem', color: '#38BDF8' },
            }}
          />

          <Button
            variant="contained"
            onClick={handleRunEvaluation}
            disabled={evaluateMutation.isPending}
            sx={{ bgcolor: '#3B82F6', mb: 3 }}
          >
            {evaluateMutation.isPending ? <CircularProgress size={20} /> : 'Run Evaluation'}
          </Button>

          {evaluateMutation.data && (
            <Box
              sx={{
                p: 2.5,
                borderRadius: 2,
                bgcolor: '#07111D',
                border: `1px solid ${
                  evaluateMutation.data.status === 'passed'
                    ? 'rgba(16, 185, 129, 0.4)'
                    : 'rgba(239, 68, 68, 0.4)'
                }`,
              }}
            >
              <Typography
                variant="subtitle1"
                fontWeight={700}
                sx={{
                  color: evaluateMutation.data.status === 'passed' ? '#34D399' : '#F87171',
                  mb: 1,
                }}
              >
                RESULT: {evaluateMutation.data.status.toUpperCase()}
              </Typography>
              <Typography variant="body2" sx={{ color: '#94A3B8' }}>
                Evaluated: {evaluateMutation.data.total_rules_evaluated} rules | Passed:{' '}
                {evaluateMutation.data.passed_rules_count} | Failed:{' '}
                {evaluateMutation.data.failed_rules_count}
              </Typography>

              {evaluateMutation.data.violations?.length > 0 && (
                <Stack spacing={1} sx={{ mt: 2 }}>
                  {evaluateMutation.data.violations.map((v, idx) => (
                    <Alert key={idx} severity="error" sx={{ bgcolor: 'rgba(239, 68, 68, 0.1)' }}>
                      <strong>{v.rule_name}</strong>: Expected <code>{v.expected_value}</code> for{' '}
                      <code>{v.claim_key}</code>, but got <code>{JSON.stringify(v.actual_value)}</code>
                    </Alert>
                  ))}
                </Stack>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setTestDialogOpen(false)} sx={{ color: '#94A3B8' }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default RulesPage;
