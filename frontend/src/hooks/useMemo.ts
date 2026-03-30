import { useMemo, useCallback } from 'react'
import { debounce, throttle } from 'lodash'

// Memoization hook for expensive computations
export function useExpensiveMemo<T>(
  factory: () => T,
  deps: React.DependencyList
): T {
  return useMemo(factory, deps)
}

// Debounced memoization hook
export function useDebouncedMemo<T>(
  factory: () => T,
  deps: React.DependencyList,
  delay: number = 300
): T {
  return useMemo(() => {
    const debouncedFactory = debounce(factory, delay)
    return debouncedFactory()
  }, deps)
}

// Throttled memoization hook
export function useThrottledMemo<T>(
  factory: () => T,
  deps: React.DependencyList,
  delay: number = 300
): T {
  return useMemo(() => {
    const throttledFactory = throttle(factory, delay)
    return throttledFactory()
  }, deps)
}

// Memoized callback hook with dependency tracking
export function useMemoizedCallback<T extends (...args: any[]) => any>(
  callback: T,
  deps: React.DependencyList
): T {
  return useCallback(callback, deps)
}

// Memoized selector hook for data transformation
export function useMemoizedSelector<T, R>(
  data: T,
  selector: (data: T) => R,
  deps: React.DependencyList = [data]
): R {
  return useMemo(() => selector(data), [data, ...deps])
}

// Memoized formatter hook
export function useMemoizedFormatter<T>(
  value: T,
  formatter: (value: T) => string,
  deps: React.DependencyList = [value]
): string {
  return useMemo(() => formatter(value), [value, ...deps])
}

// Memoized filter hook
export function useMemoizedFilter<T>(
  items: T[],
  predicate: (item: T) => boolean,
  deps: React.DependencyList = [items]
): T[] {
  return useMemo(() => items.filter(predicate), [items, ...deps])
}

// Memoized sort hook
export function useMemoizedSort<T>(
  items: T[],
  compareFn: (a: T, b: T) => number,
  deps: React.DependencyList = [items]
): T[] {
  return useMemo(() => [...items].sort(compareFn), [items, ...deps])
}

// Memoized group by hook
export function useMemoizedGroupBy<T, K extends string | number>(
  items: T[],
  keyFn: (item: T) => K,
  deps: React.DependencyList = [items]
): Record<K, T[]> {
  return useMemo(() => {
    return items.reduce((groups, item) => {
      const key = keyFn(item)
      if (!groups[key]) {
        groups[key] = []
      }
      groups[key].push(item)
      return groups
    }, {} as Record<K, T[]>)
  }, [items, ...deps])
}

// Memoized search hook
export function useMemoizedSearch<T>(
  items: T[],
  searchTerm: string,
  searchFn: (item: T, term: string) => boolean,
  deps: React.DependencyList = [items, searchTerm]
): T[] {
  return useMemo(() => {
    if (!searchTerm.trim()) return items
    return items.filter(item => searchFn(item, searchTerm.toLowerCase()))
  }, [items, searchTerm, ...deps])
}

// Memoized pagination hook
export function useMemoizedPagination<T>(
  items: T[],
  page: number,
  pageSize: number,
  deps: React.DependencyList = [items, page, pageSize]
): {
  paginatedItems: T[]
  totalPages: number
  startIndex: number
  endIndex: number
} {
  return useMemo(() => {
    const startIndex = (page - 1) * pageSize
    const endIndex = startIndex + pageSize
    const paginatedItems = items.slice(startIndex, endIndex)
    const totalPages = Math.ceil(items.length / pageSize)
    
    return {
      paginatedItems,
      totalPages,
      startIndex,
      endIndex
    }
  }, [items, page, pageSize, ...deps])
}

// Memoized aggregation hook
export function useMemoizedAggregation<T, R>(
  items: T[],
  aggregator: (items: T[]) => R,
  deps: React.DependencyList = [items]
): R {
  return useMemo(() => aggregator(items), [items, ...deps])
}

// Memoized unique values hook
export function useMemoizedUnique<T>(
  items: T[],
  keyFn?: (item: T) => any,
  deps: React.DependencyList = [items]
): T[] {
  return useMemo(() => {
    if (keyFn) {
      const seen = new Set()
      return items.filter(item => {
        const key = keyFn(item)
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
    }
    return [...new Set(items)]
  }, [items, ...deps])
}

// Memoized stats calculation hook
export function useMemoizedStats<T>(
  items: T[],
  valueFn: (item: T) => number,
  deps: React.DependencyList = [items]
): {
  count: number
  sum: number
  average: number
  min: number
  max: number
  median: number
} {
  return useMemo(() => {
    const values = items.map(valueFn).filter(val => !isNaN(val))
    const count = values.length
    
    if (count === 0) {
      return { count: 0, sum: 0, average: 0, min: 0, max: 0, median: 0 }
    }
    
    const sum = values.reduce((acc, val) => acc + val, 0)
    const average = sum / count
    const min = Math.min(...values)
    const max = Math.max(...values)
    
    // Calculate median
    const sorted = [...values].sort((a, b) => a - b)
    const median = count % 2 === 0
      ? (sorted[count / 2 - 1] + sorted[count / 2]) / 2
      : sorted[Math.floor(count / 2)]
    
    return { count, sum, average, min, max, median }
  }, [items, ...deps])
}

// Memoized chart data preparation hook
export function useMemoizedChartData<T, X, Y>(
  data: T[],
  xFn: (item: T) => X,
  yFn: (item: T) => Y,
  deps: React.DependencyList = [data]
): Array<{ x: X; y: Y }> {
  return useMemo(() => {
    return data.map(item => ({
      x: xFn(item),
      y: yFn(item)
    }))
  }, [data, ...deps])
}

// Memoized data transformation hook
export function useMemoizedTransform<T, R>(
  data: T[],
  transformFn: (items: T[]) => R,
  deps: React.DependencyList = [data]
): R {
  return useMemo(() => transformFn(data), [data, ...deps])
}

// Performance monitoring hook for memoization
export function useMemoWithPerf<T>(
  factory: () => T,
  deps: React.DependencyList,
  label: string = 'Memo'
): T {
  return useMemo(() => {
    const start = performance.now()
    const result = factory()
    const end = performance.now()
    
    if (import.meta.env.DEV) {
      console.log(`${label} computation took ${(end - start).toFixed(2)}ms`)
    }
    
    return result
  }, deps)
}

// Conditional memoization hook
export function useConditionalMemo<T>(
  factory: () => T,
  condition: boolean,
  deps: React.DependencyList
): T | undefined {
  return useMemo(() => {
    if (!condition) return undefined
    return factory()
  }, [condition, ...deps])
}

// Memoized comparison hook
export function useMemoizedComparison<T>(
  value1: T,
  value2: T,
  compareFn: (a: T, b: T) => boolean,
  deps: React.DependencyList = [value1, value2]
): boolean {
  return useMemo(() => compareFn(value1, value2), [value1, value2, ...deps])
}
