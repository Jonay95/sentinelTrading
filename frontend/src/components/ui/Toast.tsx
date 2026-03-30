import toast, { ToastOptions, ToastPosition } from 'react-hot-toast'
import { motion } from 'framer-motion'
import { clsx } from 'clsx'

// Toast configuration
const defaultOptions: ToastOptions = {
  position: 'top-right' as ToastPosition,
  duration: 4000,
  style: {
    background: 'transparent',
    boxShadow: 'none',
    padding: 0,
  },
}

// Custom toast components
export function SuccessToast({ message, t }: { message: string; t: any }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -50, scale: 0.3 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -20, scale: 0.5 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="bg-green-500 text-white px-6 py-4 rounded-lg shadow-lg flex items-center space-x-3 min-w-[300px] max-w-md"
    >
      <div className="flex-shrink-0">
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </div>
      <div className="flex-1">
        <p className="font-medium">{message}</p>
      </div>
      <button
        onClick={() => toast.dismiss(t.id)}
        className="flex-shrink-0 p-1 hover:bg-green-600 rounded transition-colors"
      >
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>
    </motion.div>
  )
}

export function ErrorToast({ message, t }: { message: string; t: any }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -50, scale: 0.3 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -20, scale: 0.5 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="bg-red-500 text-white px-6 py-4 rounded-lg shadow-lg flex items-center space-x-3 min-w-[300px] max-w-md"
    >
      <div className="flex-shrink-0">
        <svg
          className="w-6 h-6"
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
        <p className="font-medium">{message}</p>
      </div>
      <button
        onClick={() => toast.dismiss(t.id)}
        className="flex-shrink-0 p-1 hover:bg-red-600 rounded transition-colors"
      >
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>
    </motion.div>
  )
}

export function LoadingToast({ message, t }: { message: string; t: any }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -50, scale: 0.3 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -20, scale: 0.5 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="bg-blue-500 text-white px-6 py-4 rounded-lg shadow-lg flex items-center space-x-3 min-w-[300px] max-w-md"
    >
      <div className="flex-shrink-0">
        <svg
          className="w-6 h-6 animate-spin"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
          />
        </svg>
      </div>
      <div className="flex-1">
        <p className="font-medium">{message}</p>
      </div>
    </motion.div>
  )
}

export function InfoToast({ message, t }: { message: string; t: any }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -50, scale: 0.3 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -20, scale: 0.5 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="bg-blue-500 text-white px-6 py-4 rounded-lg shadow-lg flex items-center space-x-3 min-w-[300px] max-w-md"
    >
      <div className="flex-shrink-0">
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </div>
      <div className="flex-1">
        <p className="font-medium">{message}</p>
      </div>
      <button
        onClick={() => toast.dismiss(t.id)}
        className="flex-shrink-0 p-1 hover:bg-blue-600 rounded transition-colors"
      >
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>
    </motion.div>
  )
}

// Toast utility functions
export const showSuccessToast = (message: string, options: ToastOptions = {}) => {
  return toast.success((t) => <SuccessToast message={message} t={t} />, {
    ...defaultOptions,
    ...options,
  })
}

export const showErrorToast = (message: string, options: ToastOptions = {}) => {
  return toast.error((t) => <ErrorToast message={message} t={t} />, {
    ...defaultOptions,
    ...options,
  })
}

export const showLoadingToast = (message: string, options: ToastOptions = {}) => {
  return toast.loading((t) => <LoadingToast message={message} t={t} />, {
    ...defaultOptions,
    duration: Infinity, // Loading toasts don't auto-dismiss
    ...options,
  })
}

export const showInfoToast = (message: string, options: ToastOptions = {}) => {
  return toast((t) => <InfoToast message={message} t={t} />, {
    ...defaultOptions,
    ...options,
  })
}

// Specialized toast functions for common operations
export const showApiErrorToast = (error: any, defaultMessage = 'An error occurred') => {
  const message = error?.response?.data?.message || error?.message || defaultMessage
  return showErrorToast(message)
}

export const showNetworkErrorToast = () => {
  return showErrorToast('Network error. Please check your connection and try again.')
}

export const showDataSavedToast = () => {
  return showSuccessToast('Data saved successfully!')
}

export const showDataDeletedToast = () => {
  return showSuccessToast('Data deleted successfully!')
}

export const showDataUpdatedToast = () => {
  return showSuccessToast('Data updated successfully!')
}

export const showOperationLoadingToast = (operation: string) => {
  return showLoadingToast(`${operation}...`)
}

// Toast container wrapper
export function ToastProvider({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      {/* Toast container is handled by react-hot-toast */}
    </>
  )
}

// Hook for toast operations
export function useToast() {
  return {
    success: showSuccessToast,
    error: showErrorToast,
    loading: showLoadingToast,
    info: showInfoToast,
    apiError: showApiErrorToast,
    networkError: showNetworkErrorToast,
    dataSaved: showDataSavedToast,
    dataDeleted: showDataDeletedToast,
    dataUpdated: showDataUpdatedToast,
    operationLoading: showOperationLoadingToast,
    dismiss: toast.dismiss,
  }
}

// Toast styles for global configuration
export const toastStyles = {
  success: 'bg-green-500 text-white',
  error: 'bg-red-500 text-white',
  loading: 'bg-blue-500 text-white',
  info: 'bg-blue-500 text-white',
}

export default toast
