import { QueryClient, QueryCache, MutationCache } from '@tanstack/react-query'

// Create a query client with optimized caching strategies
export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error: any) => queryErrorHandler(error),
  }),
  mutationCache: new MutationCache({
    onError: (error: any) => queryErrorHandler(error),
  }),
  defaultOptions: {
    queries: {
      // Cache time: 5 minutes for most data
      staleTime: 5 * 60 * 1000,
      // Cache time: 10 minutes (data stays in cache after being stale)
      gcTime: 10 * 60 * 1000,
      // Retry failed requests 3 times with exponential backoff
      retry: 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      // Refetch on window focus
      refetchOnWindowFocus: false,
      // Refetch on reconnect
      refetchOnReconnect: true,
      // Don't refetch on mount if data is fresh
      refetchOnMount: false,
      // Enable background refetching for stale data
      refetchIntervalInBackground: true,
    },
    mutations: {
      // Retry mutations once
      retry: 1,
      retryDelay: 1000,
    },
  },
})

// Query key factory for consistent key generation
export const queryKeys = {
  // Dashboard queries
  dashboard: ['dashboard'] as const,
  dashboardData: () => [...queryKeys.dashboard, 'data'] as const,
  
  // Asset queries
  assets: ['assets'] as const,
  assetList: () => [...queryKeys.assets, 'list'] as const,
  assetDetail: (id: number) => [...queryKeys.assets, 'detail', id] as const,
  assetQuotes: (id: number) => [...queryKeys.assets, id, 'quotes'] as const,
  assetPredictions: (id: number) => [...queryKeys.assets, id, 'predictions'] as const,
  
  // News queries
  news: ['news'] as const,
  newsList: (assetId?: number) => [...queryKeys.news, 'list', assetId] as const,
  
  // Metrics queries
  metrics: ['metrics'] as const,
  walkForward: (params?: Record<string, any>) => [...queryKeys.metrics, 'walk-forward', params] as const,
  
  // Job queries
  jobs: ['jobs'] as const,
  jobStatus: (jobId: string) => [...queryKeys.jobs, 'status', jobId] as const,
}

// Query invalidation helpers
export const invalidateQueries = {
  dashboard: () => queryClient.invalidateQueries({ queryKey: queryKeys.dashboard() }),
  assets: () => queryClient.invalidateQueries({ queryKey: queryKeys.assets() }),
  asset: (id: number) => queryClient.invalidateQueries({ queryKey: queryKeys.assetDetail(id) }),
  news: () => queryClient.invalidateQueries({ queryKey: queryKeys.news() }),
  metrics: () => queryClient.invalidateQueries({ queryKey: queryKeys.metrics() }),
  jobs: () => queryClient.invalidateQueries({ queryKey: queryKeys.jobs() }),
}

// Prefetching helper
export const prefetchQueries = {
  dashboard: () => queryClient.prefetchQuery({
    queryKey: queryKeys.dashboardData(),
    queryFn: async () => {
      // This would be replaced with actual API call
      const response = await fetch('/api/dashboard')
      if (!response.ok) throw new Error('Failed to fetch dashboard data')
      return response.json()
    },
  }),
  assets: () => queryClient.prefetchQuery({
    queryKey: queryKeys.assetList(),
    queryFn: async () => {
      const response = await fetch('/api/assets')
      if (!response.ok) throw new Error('Failed to fetch assets')
      return response.json()
    },
  }),
}

// Optimistic update helpers
export const optimisticUpdates = {
  updateAsset: (id: number, updates: any) => {
    queryClient.setQueryData(
      queryKeys.assetDetail(id),
      (old: any) => old ? { ...old, ...updates } : old
    )
  },
  
  addNewsArticle: (newArticle: any) => {
    queryClient.setQueryData(
      queryKeys.newsList(),
      (old: any) => old ? [...old, newArticle] : [newArticle]
    )
  },
}

// Custom hooks for common query patterns
export const createQueryHook = <T>(
  queryKey: readonly string[],
  queryFn: () => Promise<T>,
  options: any = {}
) => {
  return () => ({
    queryKey,
    queryFn,
    ...options,
  })
}

// Background refetch configuration
export const backgroundRefetchConfig = {
  // Refetch dashboard data every 30 seconds in background
  dashboard: {
    refetchInterval: 30 * 1000, // 30 seconds
    refetchIntervalInBackground: true,
  },
  
  // Refetch market data every minute during market hours
  marketData: {
    refetchInterval: 60 * 1000, // 1 minute
    refetchIntervalInBackground: true,
    enabled: () => {
      const now = new Date()
      const hour = now.getHours()
      const day = now.getDay()
      
      // Only refetch during weekdays (Mon-Fri) and market hours (9am-5pm)
      return day >= 1 && day <= 5 && hour >= 9 && hour <= 17
    },
  },
  
  // Refetch news every 5 minutes
  news: {
    refetchInterval: 5 * 60 * 1000, // 5 minutes
    refetchIntervalInBackground: false, // News doesn't need background refetching
  },
}

// Error boundary integration
export const queryErrorHandler = (error: any) => {
  console.error('Query error:', error)
  
  // You could integrate with error reporting service here
  if (import.meta.env.PROD) {
    // Example: reportError(error)
  }
  
  // Return false to prevent default error handling
  return false
}

// Query client configuration for development vs production
export const configureQueryClient = () => {
  if (import.meta.env.DEV) {
    // Development: more aggressive refetching for debugging
    queryClient.setDefaultOptions({
      queries: {
        ...queryClient.getDefaultOptions().queries,
        staleTime: 30 * 1000, // 30 seconds in dev
        refetchOnWindowFocus: true, // Enable in dev for debugging
        retry: 1, // Less retry in dev for faster feedback
      },
    })
  } else {
    // Production: optimized for performance
    queryClient.setDefaultOptions({
      queries: {
        ...queryClient.getDefaultOptions().queries,
        staleTime: 5 * 60 * 1000, // 5 minutes in prod
        refetchOnWindowFocus: false, // Disable in prod for performance
        retry: 3, // More retry in prod for reliability
      },
    })
  }
}

export default queryClient
