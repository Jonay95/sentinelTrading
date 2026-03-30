import { type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { Skeleton } from './Skeleton'

interface LazyLoadingProps {
  children: ReactNode
  fallback?: ReactNode
  delay?: number
}

export function LazyLoading({ children, fallback, delay = 200 }: LazyLoadingProps) {
  if (delay > 0) {
    // Show fallback after delay to avoid flashing for fast loads
    return (
      <div className="relative">
        <div className="opacity-0">
          {children}
        </div>
        <div className="absolute inset-0">
          {fallback || <DashboardSkeleton />}
        </div>
      </div>
    )
  }

  return (
    <>
      {fallback || <DashboardSkeleton />}
    </>
  )
}

export function RouteLoadingFallback() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8"
    >
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <Skeleton width={200} height={32} />
        </div>
        <DashboardSkeleton />
      </div>
    </motion.div>
  )
}

// Re-export skeleton components for convenience
export { DashboardSkeleton } from './Skeleton'
