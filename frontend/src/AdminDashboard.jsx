import { useEffect, useState } from 'react'
import { AlertTriangle, RefreshCw, Trash2 } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import './admin-dashboard.css'

const PERIODS = [
  ['today', 'Hoy'], ['week', 'Esta semana'], ['month', 'Mes actual'], ['compare', 'Mes vs. anterior'],
]
const COLORS = ['#d45b3d', '#82916f', '#e4b65d', '#55746a', '#b67a58']
const money = (value) => `S/ ${Number(value || 0).toFixed(2)}`
const number = (value, digits = 0) => value == null ? '—' : `${Number(value).toFixed(digits)}`

function ChartCard({ title, subtitle, children, className = '' }) {
  return <section className={`dash-card ${className}`}><header><div><h3>{title}</h3>{subtitle && <p>{subtitle}</p>}</div></header>{children}</section>
}

export default function AdminDashboard() {
  const [period, setPeriod] = useState('today')
  const [data, setData] = useState(null)
  const [waste, setWaste] = useState({ nombre: '', cantidad: '', unidad: 'kg', motivo: '' })
  const [loading, setLoading] = useState(true)
  const [savingWaste, setSavingWaste] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function loadDashboard() {
    setLoading(true); setError('')
    try {
      const response = await fetch(`/api/admin/dashboard?period=${period}`)
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo cargar el dashboard.')
      setData(result)
    } catch (err) { setError(err.message) } finally { setLoading(false) }
  }
  useEffect(() => { loadDashboard() }, [period])

  async function saveWaste(event) {
    event.preventDefault(); setSavingWaste(true); setError(''); setNotice('')
    try {
      const response = await fetch('/api/admin/waste', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...waste, cantidad: Number(waste.cantidad) }) })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo registrar la merma.')
      setWaste({ nombre: '', cantidad: '', unidad: 'kg', motivo: '' }); setNotice('Merma registrada.'); await loadDashboard()
    } catch (err) { setError(err.message) } finally { setSavingWaste(false) }
  }

  if (loading && !data) return <p className="admin-loading">Cargando reportes...</p>
  if (error && !data) return <div className="dash-error" role="alert">{error}<button onClick={loadDashboard}>Reintentar</button></div>
  if (!data) return null
  const { resumen, operaciones, inventario, ranking, comparacion } = data
  const maxSales = Math.max(1, ...data.ventas_por_hora.map((row) => row.sales))
  const queueLevel = operaciones.cuello_de_botella ? 'critical' : operaciones.pizzas_en_cola >= operaciones.capacidad_pizzas * .7 ? 'warning' : 'good'
  const preparationLevel = operaciones.preparacion_promedio_minutos > 25 ? 'critical' : operaciones.preparacion_promedio_minutos > 18 ? 'warning' : 'good'

  return <section className="admin-dashboard" aria-label="Dashboard de reportes">
    <header className="dash-heading"><div><p className="eyebrow">RESUMEN DEL NEGOCIO</p><h2>Dashboard</h2><p>Ventas, cocina e inventario en un solo lugar.</p></div><button className="orders-refresh" onClick={loadDashboard} disabled={loading} aria-label="Actualizar dashboard"><RefreshCw size={16} /></button></header>
    {error && <p className="admin-error" role="alert">{error}</p>}{notice && <p className="admin-saved" role="status">{notice}</p>}
    <nav className="dash-periods" aria-label="Periodo del reporte">{PERIODS.map(([value, label]) => <button key={value} className={period === value ? 'active' : ''} onClick={() => setPeriod(value)}>{label}</button>)}</nav>
    <div className="dash-kpis">
      <article><span>Ventas cobradas</span><strong>{money(resumen.ventas)}</strong>{comparacion && <small>{comparacion.variacion_porcentual == null ? 'Sin base de comparación' : `${comparacion.variacion_porcentual > 0 ? '+' : ''}${comparacion.variacion_porcentual}% vs. mes anterior`}</small>}</article>
      <article><span>Pedidos pagados</span><strong>{resumen.pedidos}</strong><small>{resumen.pedidos_totales} recibidos en el periodo</small></article>
      <article><span>Ticket promedio</span><strong>{money(resumen.ticket_promedio)}</strong><small>Por pedido cobrado</small></article>
      <article><span>Clientes</span><strong>{resumen.clientes_nuevos} <i>nuevos</i></strong><small>{resumen.clientes_recurrentes} recurrentes</small></article>
    </div>
    <div className="dash-grid">
      <ChartCard title="Ventas por hora" subtitle="S/ por hora · hora local" className="dash-wide"><ResponsiveContainer width="100%" height={245}><LineChart data={data.ventas_por_hora}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e8e7df"/><XAxis dataKey="hour" interval={2} tick={{ fontSize: 10 }}/><YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `S/${v}`}/><Tooltip formatter={(value) => money(value)}/><Line type="monotone" dataKey="sales" name="Ventas" stroke="#d45b3d" strokeWidth={2.5} dot={false} activeDot={{ r: 5 }}/></LineChart></ResponsiveContainer><div className="dash-peak">Hora de mayor venta: <strong>{data.ventas_por_hora.reduce((best, row) => row.sales > best.sales ? row : best, data.ventas_por_hora[0]).hour}</strong></div></ChartCard>
      <ChartCard title="Tamaños vendidos" subtitle="Proporción de unidades"><ResponsiveContainer width="100%" height={220}><PieChart><Pie data={data.ventas_por_tamano} dataKey="value" nameKey="name" innerRadius={52} outerRadius={82} paddingAngle={3}>{data.ventas_por_tamano.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]}/>)}</Pie><Tooltip/><></></PieChart></ResponsiveContainer><div className="dash-legend">{data.ventas_por_tamano.map((row, i) => <span key={row.name}><i style={{ background: COLORS[i] }}/>{row.name}: {row.value}</span>)}</div></ChartCard>
      <ChartCard title="Top pizzas" subtitle="Por unidades vendidas"><RankList rows={ranking.top} positive/></ChartCard>
      <ChartCard title="Menor rotación" subtitle="Para evaluar promoción o cambios"><RankList rows={ranking.flop} /></ChartCard>
      <ChartCard title="Ingredientes extra" subtitle="Más pedidos en el periodo">{data.ingredientes_extra.length ? <div className="dash-bars">{data.ingredientes_extra.slice(0, 6).map((row) => <div key={row.name}><span>{row.name}</span><div><i style={{ width: `${Math.max(4, row.value / Math.max(1, ...data.ingredientes_extra.map((x) => x.value)) * 100)}%` }}/></div><b>{row.value}</b></div>)}</div> : <Empty>No hay extras registrados en este periodo.</Empty>}</ChartCard>
      <ChartCard title="Canales y formas de atención" subtitle="Canal de origen y modalidad de entrega"><div className="dash-split-tables"><div><h4>Canal de pedido</h4>{data.canales.length ? <div className="dash-table">{data.canales.map((row) => <div key={row.name}><span>{row.name}</span><strong>{money(row.sales)}</strong><small>{row.orders} pedidos</small></div>)}</div> : <Empty>Sin ventas cobradas todavía.</Empty>}</div><div><h4>Atención</h4>{data.modalidades.length ? <div className="dash-table">{data.modalidades.map((row) => <div key={row.name}><span>{row.name}</span><strong>{money(row.sales)}</strong><small>{row.orders} pedidos</small></div>)}</div> : <Empty>Sin datos.</Empty>}<h4 className="dash-payment-heading">Medios de pago</h4>{data.metodos_pago.length ? <div className="dash-table">{data.metodos_pago.map((row) => <div key={row.name}><span>{row.name}</span><strong>{money(row.sales)}</strong><small>{row.orders}</small></div>)}</div> : <Empty>Sin datos.</Empty>}</div></div></ChartCard>
      <ChartCard title="Operación de cocina" subtitle="Tiempos medidos con cambios de estado"><div className="dash-status-list"><StatusRow level={preparationLevel} label="Preparación promedio" value={operaciones.preparacion_promedio_minutos == null ? 'Sin datos' : `${number(operaciones.preparacion_promedio_minutos, 1)} min`} detail={`${operaciones.preparacion_medida} pedidos medidos`}/><StatusRow level={operaciones.delivery_promedio_minutos > 30 ? 'warning' : 'good'} label="Delivery promedio" value={operaciones.delivery_promedio_minutos == null ? 'Sin datos' : `${number(operaciones.delivery_promedio_minutos, 1)} min`} detail={`${operaciones.delivery_medidos} entregas medidas`}/><StatusRow level={queueLevel} label="Cola de cocina" value={`${operaciones.pizzas_en_cola}/${operaciones.capacidad_pizzas} pizzas`} detail={operaciones.cuello_de_botella ? 'Capacidad superada' : `${operaciones.pedidos_en_cola} pedidos en espera`}/></div></ChartCard>
      <ChartCard title="Stock crítico" subtitle="Insumos en su mínimo o por debajo">{inventario.alertas.length ? <div className="dash-stock-list">{inventario.alertas.slice(0, 6).map((row) => <div key={row.item_id} className={row.nivel === 'critico' ? 'critical' : 'warning'}><AlertTriangle size={15}/><span><strong>{row.nombre}</strong><small>{row.cantidad} {row.unidad} · mínimo {row.stock_minimo}</small></span><b>{row.nivel === 'critico' ? 'Crítico' : 'Bajo'}</b></div>)}</div> : <Empty>Sin alertas de stock.</Empty>}</ChartCard>
      <ChartCard title="Margen estimado por pizza" subtitle={data.pizzas_sin_costo ? `${data.pizzas_sin_costo} pizza(s) sin costo configurado` : 'Ventas menos costo de receta'} className="dash-wide"><div className="dash-margin-list">{data.margenes_pizza.length ? data.margenes_pizza.slice(0, 6).map((row) => <div key={row.nombre}><span>{row.nombre}</span><div className="dash-margin-track"><i style={{ width: `${Math.max(0, Math.min(100, row.porcentaje || 0))}%` }}/></div><strong>{money(row.margen)}</strong></div>) : <Empty>Agrega costos a las recetas para consultar márgenes.</Empty>}</div></ChartCard>
      <ChartCard title="Merma registrada" subtitle="Desperdicio informado para el periodo"><div className="dash-waste-list">{data.mermas.length ? data.mermas.map((row) => <span key={`${row.nombre}-${row.unidad}`}>{row.nombre}<b>{row.cantidad} {row.unidad}</b></span>) : <Empty>No hay mermas registradas.</Empty>}</div><form className="dash-waste-form" onSubmit={saveWaste}><label>Insumo<input required maxLength="120" placeholder="Ej. masa" value={waste.nombre} onChange={(e) => setWaste({ ...waste, nombre: e.target.value })}/></label><label>Cantidad<input required type="number" min="0.01" step="any" value={waste.cantidad} onChange={(e) => setWaste({ ...waste, cantidad: e.target.value })}/></label><label>Unidad<select value={waste.unidad} onChange={(e) => setWaste({ ...waste, unidad: e.target.value })}>{['kg','g','unidad','paquete','l','ml'].map((u) => <option key={u}>{u}</option>)}</select></label><label>Motivo<input maxLength="240" placeholder="Opcional" value={waste.motivo} onChange={(e) => setWaste({ ...waste, motivo: e.target.value })}/></label><button className="primary-button" disabled={savingWaste}><Trash2 size={15}/> Registrar merma</button></form></ChartCard>
    </div>
    <p className="dash-footnote">Los reportes de ventas consideran pedidos pagados. Los márgenes aparecen cuando la pizza tiene costo de receta configurado.</p>
  </section>
}

function RankList({ rows, positive = false }) {
  return rows.length ? <ol className="dash-rank">{rows.map((row, index) => <li key={row.nombre}><span className={`dash-rank-number ${positive ? 'positive' : ''}`}>{index + 1}</span><span><strong>{row.nombre}</strong><small>{row.unidades} unidades</small></span><b>{money(row.ventas)}</b></li>)}</ol> : <Empty>No hay ventas de pizzas en este periodo.</Empty>
}
function StatusRow({ level, label, value, detail }) { return <div className={`dash-status ${level}`}><i/><span><strong>{label}</strong><small>{detail}</small></span><b>{value}</b></div> }
function Empty({ children }) { return <p className="dash-empty">{children}</p> }
