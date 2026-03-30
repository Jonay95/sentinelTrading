import { Link, NavLink, Route, Routes } from 'react-router-dom'
import { Dashboard } from './pages/Dashboard'
import { AssetDetail } from './pages/AssetDetail'
import { Metrics } from './pages/Metrics'

function App() {
  return (
    <div className="app">
      <header className="header">
        <Link to="/" className="logo">
          Sentinel Trading
        </Link>
        <nav>
          <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : '')}>
            Panel
          </NavLink>
          <NavLink to="/metrics" className={({ isActive }) => (isActive ? 'active' : '')}>
            Métricas
          </NavLink>
        </nav>
      </header>
      <aside className="disclaimer">
        <strong>Aviso:</strong> esta aplicación es solo informativa y educativa. No constituye asesoramiento
        financiero. Las señales se basan en modelos estadísticos y noticias automatizadas; el rendimiento
        pasado no garantiza resultados futuros.
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/asset/:id" element={<AssetDetail />} />
          <Route path="/metrics" element={<Metrics />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
