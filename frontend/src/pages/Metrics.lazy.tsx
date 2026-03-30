import { lazy } from 'react'

export const Metrics = lazy(() => import('./Metrics').then(module => ({
  default: module.Metrics
})))
