import { lazy } from 'react'

export const Dashboard = lazy(() => import('./Dashboard').then(module => ({
  default: module.Dashboard
})))
