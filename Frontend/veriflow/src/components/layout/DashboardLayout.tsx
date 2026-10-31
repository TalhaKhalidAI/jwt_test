import React from 'react';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  List,
  Typography,
  IconButton,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Avatar,
  Chip,
  Tooltip,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  DashboardRounded as DashboardIcon,
  VpnKeyRounded as KeyIcon,
  FactCheckRounded as RulesIcon,
  AccessTimeFilledRounded as ShiftsIcon,
  QrCodeScannerRounded as ScansIcon,
  MenuRounded as MenuIcon,
  ChevronLeftRounded as ChevronLeftIcon,
  ChevronRightRounded as ChevronRightIcon,
  LogoutRounded as LogoutIcon,
  SecurityRounded as SecurityIcon,
  CircleRounded as CircleIcon,
  AdminPanelSettingsRounded as AdminIcon,
  LockResetRounded as Security2FAIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../../store/authStore';
import { useAppStore } from '../../store/appStore';
import { checkPermission, PERMISSION_MAP } from '../../HOCS/withPermissions';

const DRAWER_WIDTH = 260;
const COLLAPSED_WIDTH = 72;

export interface NavItem {
  id: string;
  title: string;
  path: string;
  icon: React.ReactElement;
  pageKey: string;
  badge?: string;
  description: string;
}

export const NAVIGATION_ITEMS: NavItem[] = [
  {
    id: 'dashboard',
    title: 'Dashboard',
    path: '/dashboard',
    icon: <DashboardIcon />,
    pageKey: 'dashboard',
    description: 'System overview & real-time telemetry',
  },
  {
    id: 'keys',
    title: 'Crypto Keys',
    path: '/keys',
    icon: <KeyIcon />,
    pageKey: 'keys',
    description: 'RS256 asymmetric keys & JWKS',
  },
  {
    id: 'rules',
    title: 'Inventory Rules',
    path: '/rules',
    icon: <RulesIcon />,
    pageKey: 'rules',
    description: 'Claim validation policies',
  },
  {
    id: 'shifts',
    title: 'Shifts & Tokens',
    path: '/shifts',
    icon: <ShiftsIcon />,
    pageKey: 'shifts',
    description: 'Worker shift sessions & QR tokens',
  },
  {
    id: 'scans',
    title: 'Scan Audits',
    path: '/scans',
    icon: <ScansIcon />,
    pageKey: 'scans',
    description: 'Offline sync & scan history',
  },
  {
    id: 'security',
    title: 'Security & 2FA',
    path: '/security',
    icon: <Security2FAIcon />,
    pageKey: 'security',
    description: 'TOTP authenticator & email OTP',
  },
  {
    id: 'admin',
    title: 'Admin Console',
    path: '/admin',
    icon: <AdminIcon />,
    pageKey: 'admin',
    description: 'Identity governance & safety controls',
  },
];

export function DashboardLayout({ children }: { children?: React.ReactNode }) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const navigate = useNavigate();
  const location = useLocation();

  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);

  const sidebarOpen = useAppStore((state) => state.sidebarOpen);
  const toggleSidebar = useAppStore((state) => state.toggleSidebar);
  const mobileSidebarOpen = useAppStore((state) => state.mobileSidebarOpen);
  const setMobileSidebarOpen = useAppStore((state) => state.setMobileSidebarOpen);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const currentWidth = sidebarOpen ? DRAWER_WIDTH : COLLAPSED_WIDTH;

  // Filter navigation items by active user permissions
  const visibleNavItems = NAVIGATION_ITEMS.filter((item) => {
    const requirement = PERMISSION_MAP[item.pageKey];
    if (!requirement) return true;
    const { allowed } = checkPermission(
      user?.permissions || {},
      requirement.permissions,
      requirement.mode,
      user?.role,
      user?.user_role
    );
    return allowed;
  });

  const drawerContent = (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: '#07111D',
        borderRight: '1px solid rgba(255, 255, 255, 0.08)',
        color: '#F8FAFC',
      }}
    >
      {/* Brand Header */}
      <Box
        sx={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          px: sidebarOpen ? 2.5 : 1.5,
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          justifyContent: sidebarOpen ? 'space-between' : 'center',
        }}
      >
        {sidebarOpen ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Box
              sx={{
                width: 34,
                height: 34,
                borderRadius: 2,
                background: 'linear-gradient(135deg, #2563EB 0%, #7C3AED 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 4px 12px rgba(37, 99, 235, 0.4)',
              }}
            >
              <SecurityIcon sx={{ fontSize: 20, color: '#fff' }} />
            </Box>
            <Box>
              <Typography variant="subtitle1" fontWeight={800} letterSpacing={0.5} lineHeight={1.1}>
                VERIFLOW
              </Typography>
              <Typography variant="caption" sx={{ color: '#94A3B8', fontSize: 10 }}>
                ENTERPRISE V1
              </Typography>
            </Box>
          </Box>
        ) : (
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: 2,
              background: 'linear-gradient(135deg, #2563EB 0%, #7C3AED 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <SecurityIcon sx={{ fontSize: 20, color: '#fff' }} />
          </Box>
        )}

        {!isMobile && sidebarOpen && (
          <IconButton size="small" onClick={toggleSidebar} sx={{ color: '#94A3B8' }}>
            <ChevronLeftIcon fontSize="small" />
          </IconButton>
        )}
      </Box>

      {/* Navigation List */}
      <List sx={{ px: 1, py: 2, flex: 1 }}>
        {visibleNavItems.map((item) => {
          const isSelected = location.pathname.startsWith(item.path);
          return (
            <ListItem key={item.id} disablePadding sx={{ display: 'block', mb: 0.5 }}>
              <Tooltip title={!sidebarOpen ? item.title : ''} placement="right">
                <ListItemButton
                  onClick={() => {
                    navigate(item.path);
                    if (isMobile) setMobileSidebarOpen(false);
                  }}
                  sx={{
                    minHeight: 46,
                    borderRadius: 2,
                    px: sidebarOpen ? 2 : 1.5,
                    justifyContent: sidebarOpen ? 'initial' : 'center',
                    bgcolor: isSelected ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                    color: isSelected ? '#60A5FA' : '#94A3B8',
                    border: isSelected ? '1px solid rgba(59, 130, 246, 0.3)' : '1px solid transparent',
                    '&:hover': {
                      bgcolor: isSelected ? 'rgba(59, 130, 246, 0.22)' : 'rgba(255, 255, 255, 0.04)',
                      color: '#F8FAFC',
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      minWidth: 0,
                      mr: sidebarOpen ? 2 : 'auto',
                      justifyContent: 'center',
                      color: isSelected ? '#60A5FA' : '#94A3B8',
                    }}
                  >
                    {item.icon}
                  </ListItemIcon>
                  {sidebarOpen && (
                    <ListItemText
                      primary={item.title}
                      primaryTypographyProps={{
                        fontSize: '0.875rem',
                        fontWeight: isSelected ? 700 : 500,
                      }}
                    />
                  )}
                  {sidebarOpen && item.badge && (
                    <Chip
                      size="small"
                      label={item.badge}
                      sx={{
                        height: 20,
                        fontSize: 10,
                        fontWeight: 700,
                        bgcolor: 'rgba(234, 179, 8, 0.2)',
                        color: '#FACC15',
                      }}
                    />
                  )}
                </ListItemButton>
              </Tooltip>
            </ListItem>
          );
        })}
      </List>

      {/* Operator Session Footer */}
      <Box
        sx={{
          p: sidebarOpen ? 2 : 1,
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          bgcolor: 'rgba(0, 0, 0, 0.2)',
        }}
      >
        {sidebarOpen ? (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, overflow: 'hidden' }}>
              <Avatar
                src={user?.profile_pic || undefined}
                sx={{
                  width: 36,
                  height: 36,
                  bgcolor: '#2563EB',
                  fontSize: 14,
                  fontWeight: 700,
                }}
              >
                {(user?.name || user?.email || 'U')[0].toUpperCase()}
              </Avatar>
              <Box sx={{ overflow: 'hidden' }}>
                <Typography variant="body2" fontWeight={600} noWrap sx={{ color: '#F8FAFC' }}>
                  {user?.name || user?.email}
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    color: '#60A5FA',
                    textTransform: 'uppercase',
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: 0.5,
                  }}
                >
                  {user?.role || user?.user_role || 'Worker'}
                </Typography>
              </Box>
            </Box>
            <Tooltip title="Log out">
              <IconButton size="small" onClick={handleLogout} sx={{ color: '#94A3B8' }}>
                <LogoutIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        ) : (
          <Tooltip title="Log out" placement="right">
            <IconButton onClick={handleLogout} sx={{ color: '#94A3B8', mx: 'auto', display: 'block' }}>
              <LogoutIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: '#020617' }}>
      {/* Mobile Drawer */}
      {isMobile ? (
        <Drawer
          variant="temporary"
          open={mobileSidebarOpen}
          onClose={() => setMobileSidebarOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{
            '& .MuiDrawer-paper': {
              width: DRAWER_WIDTH,
              boxSizing: 'border-box',
              borderRight: 'none',
            },
          }}
        >
          {drawerContent}
        </Drawer>
      ) : (
        /* Desktop Drawer */
        <Drawer
          variant="permanent"
          sx={{
            width: currentWidth,
            flexShrink: 0,
            '& .MuiDrawer-paper': {
              width: currentWidth,
              boxSizing: 'border-box',
              transition: theme.transitions.create('width', {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
              }),
              overflowX: 'hidden',
              borderRight: 'none',
            },
          }}
        >
          {drawerContent}
        </Drawer>
      )}

      {/* Main Content Area */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          width: { md: `calc(100% - ${currentWidth}px)` },
          minHeight: '100vh',
          bgcolor: '#020617',
        }}
      >
        {/* Top Navbar */}
        <AppBar
          position="sticky"
          elevation={0}
          sx={{
            bgcolor: 'rgba(7, 17, 29, 0.8)',
            backdropFilter: 'blur(12px)',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            zIndex: theme.zIndex.drawer + 1,
          }}
        >
          <Toolbar sx={{ justifyContent: 'space-between', px: { xs: 2, sm: 3 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {isMobile ? (
                <IconButton
                  color="inherit"
                  edge="start"
                  onClick={() => setMobileSidebarOpen(true)}
                  sx={{ mr: 1 }}
                >
                  <MenuIcon />
                </IconButton>
              ) : (
                !sidebarOpen && (
                  <IconButton
                    color="inherit"
                    edge="start"
                    onClick={toggleSidebar}
                    sx={{ mr: 1, color: '#94A3B8' }}
                  >
                    <ChevronRightIcon />
                  </IconButton>
                )
              )}
              <Typography variant="subtitle1" fontWeight={700} sx={{ color: '#F8FAFC' }}>
                {visibleNavItems.find((n) => location.pathname.startsWith(n.path))?.title || 'Console'}
              </Typography>
            </Box>

            {/* Status Chips */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Chip
                icon={<CircleIcon sx={{ fontSize: '8px !important', color: '#10B981 !important' }} />}
                label="API ONLINE"
                size="small"
                sx={{
                  bgcolor: 'rgba(16, 185, 129, 0.1)',
                  color: '#10B981',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  fontWeight: 700,
                  fontSize: 10,
                }}
              />
              <Chip
                label={user?.role === 'admin' ? 'ADMIN MODE' : 'WORKER'}
                size="small"
                sx={{
                  bgcolor: user?.role === 'admin' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(59, 130, 246, 0.15)',
                  color: user?.role === 'admin' ? '#EF4444' : '#60A5FA',
                  border: `1px solid ${user?.role === 'admin' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(59, 130, 246, 0.3)'}`,
                  fontWeight: 700,
                  fontSize: 10,
                }}
              />
            </Box>
          </Toolbar>
        </AppBar>

        {/* Dynamic Route View */}
        <Box sx={{ flexGrow: 1, p: { xs: 2, sm: 3 } }}>
          {children || <Outlet />}
        </Box>
      </Box>
    </Box>
  );
}

export default DashboardLayout;
