import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import {
  getPredictions,
  getQuotes,
  getNews,
  type Signal,
} from '../api'
import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

const signalLabel: Record<Signal, string> = {
  buy: 'Comprar',
  sell: 'Vender',
  hold: 'Mantener',
}

export function AssetDetail() {
  const { id } = useParams()
  const assetId = Number(id)

  const quotes = useQuery({
    queryKey: ['quotes', assetId],
    queryFn: () => getQuotes(assetId),
    enabled: Number.isFinite(assetId),
  })

  const preds = useQuery({
    queryKey: ['predictions', assetId],
    queryFn: () => getPredictions(assetId),
    enabled: Number.isFinite(assetId),
  })

  const news = useQuery({
    queryKey: ['news', assetId],
    queryFn: () => getNews(assetId),
    enabled: Number.isFinite(assetId),
  })

  const chartData =
    quotes.data?.map((q) => ({
      t: q.ts.slice(0, 10),
      close: q.close,
    })) ?? []

  if (!Number.isFinite(assetId)) {
    return <p>Activo no válido</p>
  }

  return (
    <div>
      <p>
        <Link to="/">← Volver</Link>
      </p>
      <h1>Activo #{assetId}</h1>
      {quotes.isLoading && <p>Cargando cotizaciones…</p>}
      {quotes.error && <p className="error">Error al cargar cotizaciones.</p>}
      {chartData.length > 0 && (
        <section className="section">
          <h2>Precio de cierre</h2>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={320}>
              <ComposedChart data={chartData}>
                <XAxis dataKey="t" />
                <YAxis domain={['auto', 'auto']} />
                <Tooltip />
                <Legend />
                <Line dataKey="close" name="Cierre" stroke="var(--accent)" dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      <section className="section">
        <h2>Histórico de predicciones</h2>
        {preds.isLoading && <p>Cargando…</p>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Señal</th>
                <th>Conf.</th>
                <th>Base</th>
                <th>Predicho</th>
                <th>Real (eval.)</th>
              </tr>
            </thead>
            <tbody>
              {(preds.data ?? []).map((p) => (
                <tr key={p.id}>
                  <td>{p.created_at.slice(0, 19)}</td>
                  <td>{signalLabel[p.signal]}</td>
                  <td>{(p.confidence * 100).toFixed(0)}%</td>
                  <td>{p.base_price.toFixed(4)}</td>
                  <td>{p.predicted_value.toFixed(4)}</td>
                  <td>
                    {p.outcome
                      ? `${p.outcome.actual_value.toFixed(4)} (${p.outcome.evaluated_at.slice(0, 10)})`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section">
        <h2>Noticias recientes (sentimiento)</h2>
        {news.isLoading && <p>Cargando noticias…</p>}
        {!news.data?.length && !news.isLoading && (
          <p className="muted">
            No hay noticias indexadas. Configura NEWS_API_KEY en el backend o ejecuta el job de noticias tras
            tener clave.
          </p>
        )}
        <ul className="news-list">
          {(news.data ?? []).map((n) => (
            <li key={n.id}>
              <span className="news-sent">{n.sentiment != null ? n.sentiment.toFixed(2) : '—'}</span>
              {n.url ? (
                <a href={n.url} target="_blank" rel="noreferrer">
                  {n.title}
                </a>
              ) : (
                n.title
              )}
              <span className="muted"> · {n.published_at.slice(0, 10)}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
