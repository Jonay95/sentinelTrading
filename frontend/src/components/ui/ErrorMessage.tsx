import { motion } from 'framer-motion'
import { clsx } from 'clsx'

interface ErrorMessageProps {
  error?: Error | string | null
  fallback?: string
  className?: string
  showIcon?: boolean
  variant?: 'default' | 'inline' | 'card'
  action?: {
    label: string
    onClick: () => void
  }
}

export function ErrorMessage({
  error,
  fallback = 'An unexpected error occurred',
  className,
  showIcon = true,
  variant = 'default',
  action
}: ErrorMessageProps) {
  if (!error) return null

  const errorMessage = typeof error === 'string' ? error : error?.message || fallback

  const baseClasses = clsx(
    'text-red-600 dark:text-red-400',
    className
  )

  const iconClasses = clsx(
    'w-5 h-5',
    variant === 'inline' ? 'w-4 h-4' : 'w-5 h-5'
  )

  if (variant === 'inline') {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className={clsx(baseClasses, 'flex items-center space-x-2 text-sm')}
      >
        {showIcon && (
          <svg
            className={iconClasses}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        )}
        <span>{errorMessage}</span>
      </motion.div>
    )
  }

  if (variant === 'card') {
    return (
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4"
      >
        <div className="flex items-start space-x-3">
          {showIcon && (
            <div className="flex-shrink-0">
              <svg
                className={iconClasses}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
          )}
          <div className="flex-1">
            <h3 className="text-sm font-medium text-red-800 dark:text-red-200">
              Error
            </h3>
            <p className="mt-1 text-sm text-red-700 dark:text-red-300">
              {errorMessage}
            </p>
            {action && (
              <div className="mt-3">
                <button
                  onClick={action.onClick}
                  className="text-sm font-medium text-red-600 dark:text-red-400 hover:text-red-500 dark:hover:text-red-300 transition-colors"
                >
                  {action.label}
                </button>
              </div>
            )}
          </div>
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx(baseClasses, 'flex items-center space-x-2')}
    >
      {showIcon && (
        <svg
          className={iconClasses}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      )}
      <span>{errorMessage}</span>
    </motion.div>
  )
}

// Specialized error message components
export function NetworkError({ onRetry }: { onRetry?: () => void }) {
  return (
    <ErrorMessage
      error="Unable to connect to the server. Please check your internet connection and try again."
      variant="card"
      action={onRetry ? { label: 'Retry', onClick: onRetry } : undefined}
    />
  )
}

export function DataLoadError({ onRetry }: { onRetry?: () => void }) {
  return (
    <ErrorMessage
      error="Failed to load data. Please refresh the page and try again."
      variant="card"
      action={onRetry ? { label: 'Refresh', onClick: onRetry } : undefined}
    />
  )
}

export function ValidationError({ errors }: { errors: string[] | Record<string, string> }) {
  const errorList = Array.isArray(errors) ? errors : Object.values(errors)

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4"
    >
      <div className="flex items-start space-x-3">
        <div className="flex-shrink-0">
          <svg
            className="w-5 h-5 text-red-600 dark:text-red-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-medium text-red-800 dark:text-red-200 mb-2">
            Validation Error
          </h3>
          <ul className="text-sm text-red-700 dark:text-red-300 space-y-1">
            {errorList.map((error, index) => (
              <li key={index} className="flex items-start space-x-2">
                <span className="text-red-500 mt-0.5">•</span>
                <span>{error}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </motion.div>
  )
}

export function ApiError({ 
  error, 
  onRetry 
}: { 
  error: any
  onRetry?: () => void 
}) {
  const getMessage = (error: any): string => {
    if (typeof error === 'string') return error
    
    // Check for common API error patterns
    if (error?.response?.data?.message) {
      return error.response.data.message
    }
    
    if (error?.response?.data?.error) {
      return error.response.data.error
    }
    
    if (error?.message) {
      return error.message
    }
    
    // Handle HTTP status codes
    if (error?.response?.status === 401) {
      return 'Authentication required. Please log in again.'
    }
    
    if (error?.response?.status === 403) {
      return 'You do not have permission to perform this action.'
    }
    
    if (error?.response?.status === 404) {
      return 'The requested resource was not found.'
    }
    
    if (error?.response?.status === 429) {
      return 'Too many requests. Please wait a moment and try again.'
    }
    
    if (error?.response?.status >= 500) {
      return 'Server error. Please try again later.'
    }
    
    return 'An unexpected error occurred. Please try again.'
  }

  return (
    <ErrorMessage
      error={getMessage(error)}
      variant="card"
      action={onRetry ? { label: 'Retry', onClick: onRetry } : undefined}
    />
  )
}

// Hook for error handling
export function useErrorHandler() {
  const handleError = (error: any, fallback?: string) => {
    console.error('Error handled by useErrorHandler:', error)
    
    // You could integrate with error reporting service here
    if (import.meta.env.PROD) {
      // Example: reportError(error)
    }
    
    return error?.message || fallback || 'An unexpected error occurred'
  }

  const isNetworkError = (error: any): boolean => {
    return (
      error?.code === 'NETWORK_ERROR' ||
      error?.message?.includes('fetch') ||
      error?.message?.includes('network') ||
      !navigator.onLine
    )
  }

  const isValidationError = (error: any): boolean => {
    return (
      error?.response?.status === 422 ||
      error?.response?.status === 400 ||
      Array.isArray(error?.response?.data?.errors) ||
      typeof error?.response?.data?.errors === 'object'
    )
  }

  return {
    handleError,
    isNetworkError,
    isValidationError,
  }
}
