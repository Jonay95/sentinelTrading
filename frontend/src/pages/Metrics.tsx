import { useMutation, useQuery } from '@tanstack/react-query'
import {
  getMetricsSummary,
  getMetricsByAsset,
  getModelRecommendation,
  getWalkForward,
  type WalkForwardAll,
  type WalkForwardRow,
} from '../api'

function isWalkForwardRow(x: unknown): x is WalkForwardRow {
  if (typeof x !== 'object' || x === null) return false
  const o = x as Record<string, unknown>
  return typeof o.n_steps === 'number' && typeof o.mean_abs_pct_error === 'number'
}

export function Metrics() {
  const summary = useQuery({
    queryKey: ['metrics-summary'],
    queryFn: () => getMetricsSummary(90),
  })
  const byAsset = useQuery({
    queryKey: ['metrics-by-asset'],
    queryFn: () => getMetricsByAsset(90),
  })
  const rec = useQuery({
    queryKey: ['model-rec'],
    queryFn: () => getModelRecommendation(90),
  })

  const wf = useMutation({
    mutationFn: () => getWalkForward({ trainMin: 55, step: 3, ensemble: true }),
  })

  const wfData = wf.data as WalkForwardAll | WalkForwardRow | undefined
  const wfRows: WalkForwardRow[] =
    wfData && 'assets' in wfData
      ? wfData.assets.filter(isWalkForwardRow)
      : wfData && isWalkForwardRow(wfData)
        ? [wfData]
        : []

  return (
    <div>
      <h1>Métricas de precisión</h1>
      <p className="muted">
        Errores basados en predicciones ya evaluadas en producción. El modelo actual combina ARIMA + suavizado
        exponencial (ETS), umbral adaptativo a la volatilidad y filtro de volatilidad extrema. Configura
        variables en <code className="inline-code">backend/.env</code> (ver README).
      </p>

      <section className="section">
        <h2>Backtest walk-forward</h2>
        <p className="muted">
          Simula predicciones paso a paso solo con datos históricos (no guarda filas en la base de datos).
          Puede tardar unos segundos.
        </p>
        <button
          type="button"
          className="btn-primary"
          disabled={wf.isPending}
          onClick={() => wf.mutate()}
        >
          {wf.isPending ? 'Calculando…' : 'Ejecutar walk-forward (todos los activos)'}
        </button>
        {wf.isError && <p className="error">Error al contactar el backend.</p>}
        {wfRows.length > 0 && (
          <div className="table-wrap" style={{ marginTop: '1rem' }}>
            <table>
              <thead>
                <tr>
                  <th>Símbolo</th>
                  <th>Pasos</th>
                  <th>MAPE medio</th>
                  <th>Acierto dirección</th>
                  <th>Coincidencia señal</th>
                </tr>
              </thead>
              <tbody>
                {wfRows.map((r) => (
                  <tr key={r.asset_id}>
                    <td>{r.symbol ?? r.asset_id}</td>
                    <td>{r.n_steps}</td>
                    <td>{(r.mean_abs_pct_error * 100).toFixed(2)}%</td>
                    <td>{(r.directional_accuracy * 100).toFixed(1)}%</td>
                    <td>{(r.signal_match_rate * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="section">
        <h2>Recomendación de versión</h2>
        {rec.isLoading && <p>Cargando…</p>}
        {rec.data && 'message' in rec.data && <p className="muted">{rec.data.message}</p>}
        {rec.data && 'recommended_version' in rec.data && (
          <div className="callout">
            <p>
              Mejor versión en la ventana: <strong>{rec.data.recommended_version}</strong>
            </p>
            <p>
              Error medio (aprox.): {(rec.data.mean_abs_pct_error * 100).toFixed(2)}% · muestras:{' '}
              {rec.data.sample_count}
            </p>
          </div>
        )}
      </section>

      <section className="section">
        <h2>Por versión de modelo</h2>
        {summary.isLoading && <p>Cargando…</p>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Versión</th>
                <th>N evaluadas</th>
                <th>Error medio % (aprox.)</th>
              </tr>
            </thead>
            <tbody>
              {(summary.data?.by_version ?? []).map((v) => (
                <tr key={v.model_version}>
                  <td>{v.model_version}</td>
                  <td>{v.count}</td>
                  <td>{(v.mean_abs_pct_error * 100).toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section">
        <h2>Por activo</h2>
        {byAsset.isLoading && <p>Cargando…</p>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Símbolo</th>
                <th>Predicciones evaluadas</th>
                <th>Error medio % (aprox.)</th>
              </tr>
            </thead>
            <tbody>
              {(byAsset.data ?? []).map((r) => (
                <tr key={r.asset_id}>
                  <td>{r.symbol}</td>
                  <td>{r.evaluated_predictions}</td>
                  <td>{(r.mean_abs_pct_error * 100).toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
