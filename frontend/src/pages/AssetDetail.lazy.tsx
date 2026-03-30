import { lazy } from 'react'

export const AssetDetail = lazy(() => import('./AssetDetail').then(module => ({
  default: module.AssetDetail
})))
