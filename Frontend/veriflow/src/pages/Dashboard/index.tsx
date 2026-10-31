import { useNavigate } from 'react-router-dom';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  Stack,
  CircularProgress,
} from '@mui/material';
import {
  VpnKeyRounded as KeyIcon,
  FactCheckRounded as RuleIcon,
  AccessTimeFilledRounded as ShiftIcon,
  QrCodeScannerRounded as ScanIcon,
  ArrowForwardRounded as ArrowIcon,
  CheckCircleRounded as CheckIcon,
} from '@mui/icons-material';
import ReactECharts from 'echarts-for-react';
import { useDashboardOverviewQuery } from './query';
import { useAuthStore } from '../../store/authStore';

export function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const { data: stats, isLoading } = useDashboardOverviewQuery();

  const chartOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0F172A',
      borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#F8FAFC' },
    },
    legend: {
      data: ['Valid Scans', 'Violations'],
      textStyle: { color: '#94A3B8' },
      top: 0,
      right: 10,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '40px',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: ['08:00', '10:00', '12:00', '14:00', '16:00', '18:00', 'Now'],
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
      axisLabel: { color: '#64748B' },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
      axisLabel: { color: '#64748B' },
    },
    series: [
      {
        name: 'Valid Scans',
        type: 'line',
        smooth: true,
        data: [12, 28, 45, 60, 52, 70, stats?.validScansCount || 85],
        itemStyle: { color: '#10B981' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(16, 185, 129, 0.35)' },
              { offset: 1, color: 'rgba(16, 185, 129, 0.0)' },
            ],
          },
        },
      },
      {
        name: 'Violations',
        type: 'line',
        smooth: true,
        data: [1, 2, 0, 3, 1, 4, stats?.invalidScansCount || 2],
        itemStyle: { color: '#EF4444' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(239, 68, 68, 0.35)' },
              { offset: 1, color: 'rgba(239, 68, 68, 0.0)' },
            ],
          },
        },
      },
    ],
  };

  return (
    <Box sx={{ maxWidth: 1400, mx: 'auto' }}>
      {/* Welcome Banner */}
      <Box sx={{ mb: 4 }}>
        <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mb: 1 }}>
          <Chip
            size="small"
            label="SYSTEM OPERATIONAL"
            icon={<CheckIcon sx={{ fontSize: '14px !important', color: '#10B981 !important' }} />}
            sx={{
              bgcolor: 'rgba(16, 185, 129, 0.1)',
              color: '#34D399',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              fontWeight: 700,
            }}
          />
          <Typography variant="caption" sx={{ color: '#64748B' }}>
            RS256 Offline Asymmetric Cryptography Enabled
          </Typography>
        </Stack>

        <Typography variant="h4" fontWeight={800} sx={{ letterSpacing: -0.5 }}>
          Welcome back, {user?.name || user?.email?.split('@')[0] || 'Operator'}
        </Typography>
        <Typography variant="body2" sx={{ color: '#94A3B8', mt: 0.5 }}>
          Real-time security telemetry, active cryptographic keys, and warehouse inventory verification status.
        </Typography>
      </Box>

      {/* 4 Stat Cards */}
      <Grid container spacing={2.5} sx={{ mb: 4 }}>
        {/* Card 1: Crypto Keys */}
        <Grid item xs={12} sm={6} md={3}>
          <Card
            sx={{
              bgcolor: '#0B132B',
              borderRadius: 3,
              border: '1px solid rgba(59, 130, 246, 0.2)',
              boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
              cursor: 'pointer',
              transition: 'transform 0.15s ease',
              '&:hover': { transform: 'translateY(-2px)' },
            }}
            onClick={() => navigate('/keys')}
          >
            <CardContent sx={{ p: 2.5 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                <Typography variant="caption" sx={{ color: '#94A3B8', fontWeight: 600 }}>
                  ACTIVE RSA KEYS
                </Typography>
                <Box
                  sx={{
                    width: 32,
                    height: 32,
                    borderRadius: 1.5,
                    bgcolor: 'rgba(59, 130, 246, 0.15)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#60A5FA',
                  }}
                >
                  <KeyIcon fontSize="small" />
                </Box>
              </Box>

              <Typography variant="h3" fontWeight={800} sx={{ color: '#F8FAFC' }}>
                {isLoading ? <CircularProgress size={28} /> : stats?.activeKeysCount ?? 0}
              </Typography>
              <Typography variant="caption" sx={{ color: '#60A5FA', display: 'flex', alignItems: 'center', gap: 0.5, mt: 1 }}>
                Manage Keys & JWKS <ArrowIcon sx={{ fontSize: 14 }} />
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Card 2: Inventory Rules */}
        <Grid item xs={12} sm={6} md={3}>
          <Card
            sx={{
              bgcolor: '#0B132B',
              borderRadius: 3,
              border: '1px solid rgba(250, 204, 21, 0.2)',
              boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
              cursor: 'pointer',
              transition: 'transform 0.15s ease',
              '&:hover': { transform: 'translateY(-2px)' },
            }}
            onClick={() => navigate('/rules')}
          >
            <CardContent sx={{ p: 2.5 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                <Typography variant="caption" sx={{ color: '#94A3B8', fontWeight: 600 }}>
                  ENFORCED POLICIES
                </Typography>
                <Box
                  sx={{
                    width: 32,
                    height: 32,
                    borderRadius: 1.5,
                    bgcolor: 'rgba(250, 204, 21, 0.15)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#FACC15',
                  }}
                >
                  <RuleIcon fontSize="small" />
                </Box>
              </Box>

              <Typography variant="h3" fontWeight={800} sx={{ color: '#F8FAFC' }}>
                {isLoading ? <CircularProgress size={28} /> : stats?.activeRulesCount ?? 0}
              </Typography>
              <Typography variant="caption" sx={{ color: '#FACC15', display: 'flex', alignItems: 'center', gap: 0.5, mt: 1 }}>
                Configure Rules Matrix <ArrowIcon sx={{ fontSize: 14 }} />
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Card 3: Active Shift */}
        <Grid item xs={12} sm={6} md={3}>
          <Card
            sx={{
              bgcolor: '#0B132B',
              borderRadius: 3,
              border: `1px solid ${
                stats?.hasActiveShift ? 'rgba(16, 185, 129, 0.3)' : 'rgba(148, 163, 184, 0.2)'
              }`,
              boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
              cursor: 'pointer',
              transition: 'transform 0.15s ease',
              '&:hover': { transform: 'translateY(-2px)' },
            }}
            onClick={() => navigate('/shifts')}
          >
            <CardContent sx={{ p: 2.5 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                <Typography variant="caption" sx={{ color: '#94A3B8', fontWeight: 600 }}>
                  WORK SHIFT STATUS
                </Typography>
                <Box
                  sx={{
                    width: 32,
                    height: 32,
                    borderRadius: 1.5,
                    bgcolor: stats?.hasActiveShift
                      ? 'rgba(16, 185, 129, 0.15)'
                      : 'rgba(148, 163, 184, 0.15)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: stats?.hasActiveShift ? '#34D399' : '#94A3B8',
                  }}
                >
                  <ShiftIcon fontSize="small" />
                </Box>
              </Box>

              <Typography
                variant="h4"
                fontWeight={800}
                sx={{
                  color: stats?.hasActiveShift ? '#34D399' : '#94A3B8',
                  mt: 0.5,
                  mb: 0.5,
                }}
              >
                {isLoading ? <CircularProgress size={28} /> : stats?.hasActiveShift ? 'ON DUTY' : 'STANDBY'}
              </Typography>
              <Typography variant="caption" sx={{ color: '#34D399', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                View Shift & Tokens <ArrowIcon sx={{ fontSize: 14 }} />
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Card 4: Scans Telemetry */}
        <Grid item xs={12} sm={6} md={3}>
          <Card
            sx={{
              bgcolor: '#0B132B',
              borderRadius: 3,
              border: '1px solid rgba(168, 85, 247, 0.2)',
              boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
              cursor: 'pointer',
              transition: 'transform 0.15s ease',
              '&:hover': { transform: 'translateY(-2px)' },
            }}
            onClick={() => navigate('/scans')}
          >
            <CardContent sx={{ p: 2.5 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                <Typography variant="caption" sx={{ color: '#94A3B8', fontWeight: 600 }}>
                  TOTAL AUDIT SCANS
                </Typography>
                <Box
                  sx={{
                    width: 32,
                    height: 32,
                    borderRadius: 1.5,
                    bgcolor: 'rgba(168, 85, 247, 0.15)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#C084FC',
                  }}
                >
                  <ScanIcon fontSize="small" />
                </Box>
              </Box>

              <Typography variant="h3" fontWeight={800} sx={{ color: '#F8FAFC' }}>
                {isLoading ? <CircularProgress size={28} /> : stats?.totalScansCount ?? 0}
              </Typography>
              <Typography variant="caption" sx={{ color: '#C084FC', display: 'flex', alignItems: 'center', gap: 0.5, mt: 1 }}>
                Inspect Scans Log <ArrowIcon sx={{ fontSize: 14 }} />
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Chart Section */}
      <Card
        sx={{
          bgcolor: '#0B132B',
          borderRadius: 3,
          border: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
          p: 3,
          mb: 4,
        }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box>
            <Typography variant="subtitle1" fontWeight={700}>
              Verification Telemetry Over Time
            </Typography>
            <Typography variant="caption" sx={{ color: '#94A3B8' }}>
              Real-time trend of valid vs violation scans captured by online and offline devices.
            </Typography>
          </Box>
          <Chip label="LIVE STREAMING" size="small" sx={{ bgcolor: 'rgba(59, 130, 246, 0.15)', color: '#60A5FA', fontWeight: 600 }} />
        </Box>

        <Box sx={{ height: 320, width: '100%' }}>
          <ReactECharts option={chartOption} style={{ height: '100%', width: '100%' }} />
        </Box>
      </Card>

      {/* Quick Action Shortcuts */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
          Security Action Shortcuts
        </Typography>

        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}>
            <Button
              fullWidth
              variant="outlined"
              onClick={() => navigate('/shifts')}
              sx={{
                p: 2,
                justifyContent: 'flex-start',
                textAlign: 'left',
                borderColor: 'rgba(255, 255, 255, 0.1)',
                color: '#F8FAFC',
                '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.04)', borderColor: '#10B981' },
              }}
            >
              <ShiftIcon sx={{ mr: 1.5, color: '#10B981' }} />
              <Box>
                <Typography variant="body2" fontWeight={600}>
                  Launch Work Shift
                </Typography>
                <Typography variant="caption" sx={{ color: '#94A3B8' }}>
                  Generate on-screen QR
                </Typography>
              </Box>
            </Button>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Button
              fullWidth
              variant="outlined"
              onClick={() => navigate('/keys')}
              sx={{
                p: 2,
                justifyContent: 'flex-start',
                textAlign: 'left',
                borderColor: 'rgba(255, 255, 255, 0.1)',
                color: '#F8FAFC',
                '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.04)', borderColor: '#3B82F6' },
              }}
            >
              <KeyIcon sx={{ mr: 1.5, color: '#3B82F6' }} />
              <Box>
                <Typography variant="body2" fontWeight={600}>
                  Rotate Crypto Key
                </Typography>
                <Typography variant="caption" sx={{ color: '#94A3B8' }}>
                  Generate new primary RSA
                </Typography>
              </Box>
            </Button>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Button
              fullWidth
              variant="outlined"
              onClick={() => navigate('/rules')}
              sx={{
                p: 2,
                justifyContent: 'flex-start',
                textAlign: 'left',
                borderColor: 'rgba(255, 255, 255, 0.1)',
                color: '#F8FAFC',
                '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.04)', borderColor: '#FACC15' },
              }}
            >
              <RuleIcon sx={{ mr: 1.5, color: '#FACC15' }} />
              <Box>
                <Typography variant="body2" fontWeight={600}>
                  Add Inventory Rule
                </Typography>
                <Typography variant="caption" sx={{ color: '#94A3B8' }}>
                  Enforce tag claim check
                </Typography>
              </Box>
            </Button>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Button
              fullWidth
              variant="outlined"
              onClick={() => navigate('/scans')}
              sx={{
                p: 2,
                justifyContent: 'flex-start',
                textAlign: 'left',
                borderColor: 'rgba(255, 255, 255, 0.1)',
                color: '#F8FAFC',
                '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.04)', borderColor: '#C084FC' },
              }}
            >
              <ScanIcon sx={{ mr: 1.5, color: '#C084FC' }} />
              <Box>
                <Typography variant="body2" fontWeight={600}>
                  Verify Raw Token
                </Typography>
                <Typography variant="caption" sx={{ color: '#94A3B8' }}>
                  Offline signature test
                </Typography>
              </Box>
            </Button>
          </Grid>
        </Grid>
      </Box>
    </Box>
  );
}

export default DashboardPage;
