import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  getDashboard,
  getQuotes,
  postFullPipeline,
  type DashboardRow,
  type Signal,
} from '../api'
import {
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useMemo } from 'react'

const signalLabel: Record<Signal, string> = {
  buy: 'Comprar',
  sell: 'Vender',
  hold: 'Mantener',
}

const signalClass: Record<Signal, string> = {
  buy: 'signal-buy',
  sell: 'signal-sell',
  hold: 'signal-hold',
}

function MiniSparkline({ assetId }: { assetId: number }) {
  const { data } = useQuery({
    queryKey: ['quotes-mini', assetId],
    queryFn: async () => {
      const pts = await getQuotes(assetId)
      return pts.slice(-14).map((p) => ({ t: p.ts.slice(5, 10), c: p.close }))
    },
  })
  if (!data?.length) return <div className="spark-empty">Sin datos</div>
  return (
    <div className="spark">
      <ResponsiveContainer width="100%" height={48}>
        <LineChart data={data}>
          <XAxis dataKey="t" hide />
          <YAxis domain={['auto', 'auto']} hide />
          <Tooltip formatter={(v) => (typeof v === 'number' ? v.toFixed(2) : String(v))} />
          <Line type="monotone" dataKey="c" stroke="var(--accent)" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function Card({ row }: { row: DashboardRow }) {
  const pred = row.latest_prediction
  const sig = pred?.signal
  return (
    <article className="card">
      <div className="card-head">
        <div>
          <h2>
            <Link to={`/asset/${row.asset.id}`}>{row.asset.symbol}</Link>
          </h2>
          <p className="muted">{row.asset.name}</p>
          <span className="badge">{row.asset.asset_type}</span>
        </div>
        {sig && (
          <span className={`pill ${signalClass[sig]}`}>{signalLabel[sig]}</span>
        )}
      </div>
      <MiniSparkline assetId={row.asset.id} />
      {row.last_quote && (
        <p className="price">
          Último cierre: <strong>{row.last_quote.close.toFixed(4)}</strong>
          <span className="muted"> · {row.last_quote.ts.slice(0, 10)}</span>
        </p>
      )}
      {pred && (
        <ul className="meta">
          <li>Confianza: {(pred.confidence * 100).toFixed(0)}%</li>
          <li>Objetivo: {pred.predicted_value.toFixed(4)}</li>
          <li>Modelo: {pred.model_version}</li>
        </ul>
      )}
      {!pred && <p className="muted">Sin predicción aún. Ejecuta la ingesta y el pipeline.</p>}
    </article>
  )
}

export function Dashboard() {
  const qc = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
  })

  const mutation = useMutation({
    mutationFn: () => postFullPipeline(false),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['quotes-mini'] })
    },
  })

  const sorted = useMemo(() => {
    if (!data) return []
    return [...data].sort((a, b) => a.asset.symbol.localeCompare(b.asset.symbol))
  }, [data])

  return (
    <div>
      <div className="toolbar">
        <h1>Panel</h1>
        <button
          type="button"
          className="btn-primary"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? 'Ejecutando…' : 'Actualizar datos y predicciones'}
        </button>
      </div>
      {mutation.isError && (
        <p className="error">Error al llamar al backend. ¿Está Flask en el puerto 5000?</p>
      )}
      {isLoading && <p>Cargando…</p>}
      {error && <p className="error">No se pudo cargar el panel.</p>}
      <div className="grid">
        {sorted.map((row) => (
          <Card key={row.asset.id} row={row} />
        ))}
      </div>
    </div>
  )
}
