import { clsx } from 'clsx'

interface SkeletonProps {
  className?: string
  variant?: 'default' | 'text' | 'circular' | 'rectangular'
  width?: string | number
  height?: string | number
  animation?: 'pulse' | 'wave' | 'none'
}

export function Skeleton({
  className,
  variant = 'default',
  width,
  height,
  animation = 'pulse',
  ...props
}: SkeletonProps) {
  const variantClasses = {
    default: 'rounded-md',
    text: 'rounded',
    circular: 'rounded-full',
    rectangular: 'rounded-none'
  }

  const animationClasses = {
    pulse: 'animate-pulse',
    wave: 'animate-shimmer',
    none: ''
  }

  return (
    <div
      className={clsx(
        'bg-gray-200 dark:bg-gray-700',
        variantClasses[variant],
        animationClasses[animation],
        className
      )}
      style={{
        width: width || '100%',
        height: height || '1rem'
      }}
      {...props}
    />
  )
}

// Predefined skeleton components for common use cases
export function CardSkeleton() {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 space-y-4">
      <div className="flex items-center space-x-4">
        <Skeleton variant="circular" width={40} height={40} />
        <div className="flex-1 space-y-2">
          <Skeleton width="60%" height={20} />
          <Skeleton width="40%" height={16} />
        </div>
      </div>
      <div className="space-y-2">
        <Skeleton height={16} />
        <Skeleton height={16} />
        <Skeleton width="80%" height={16} />
      </div>
    </div>
  )
}

export function TableRowSkeleton() {
  return (
    <tr className="border-b dark:border-gray-700">
      <td className="p-4"><Skeleton width={100} height={20} /></td>
      <td className="p-4"><Skeleton width={80} height={20} /></td>
      <td className="p-4"><Skeleton width={120} height={20} /></td>
      <td className="p-4"><Skeleton width={60} height={20} /></td>
      <td className="p-4"><Skeleton width={80} height={20} /></td>
    </tr>
  )
}

export function ChartSkeleton() {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-4">
        <Skeleton width={150} height={24} />
        <Skeleton width={100} height={32} />
      </div>
      <div className="space-y-2">
        <Skeleton height={300} />
        <div className="flex justify-between">
          <Skeleton width={60} height={16} />
          <Skeleton width={60} height={16} />
          <Skeleton width={60} height={16} />
          <Skeleton width={60} height={16} />
        </div>
      </div>
    </div>
  )
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            <Skeleton width={80} height={16} className="mb-2" />
            <Skeleton width={120} height={32} />
            <Skeleton width={60} height={12} className="mt-2" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartSkeleton />
        <div className="space-y-4">
          <Skeleton width={150} height={24} />
          {[...Array(5)].map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      </div>
    </div>
  )
}
