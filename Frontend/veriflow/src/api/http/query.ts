// src/api/http/query.ts
import { QueryClient } from '@tanstack/react-query';
import { ToastMsgs } from '../toastUtils';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnMount: false,
      staleTime: 15 * 60 * 1000,
      refetchOnReconnect: false,
      refetchOnWindowFocus: false,
      
      // ✅ ADD THIS: Handle query errors
      throwOnError: (error: any) => {
        if (error?.status !== 401) {
          ToastMsgs.error(error?.message || 'Failed to load data');
        }
        return true;
      },
    },
    mutations: {
      // ✅ ADD THIS: Handle mutation errors
      onError: (error: any) => {
        if (error?.status !== 401) {
          ToastMsgs.error(error?.message || 'Operation failed');
        }
      },
    },
 
  },
});