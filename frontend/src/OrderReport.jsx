import { useEffect, useState } from 'react'
import { apiJson } from './api.js'

const cash = (value) => `S/ ${Number(value).toFixed(2)}`
export default function OrderReport() {
  const [filters, setFilters] = useState({ desde: '', hasta: '', estado: '' })
  const [query, setQuery] = useState('')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true; setError('')
    apiJson(`/api/admin/reports?${query}`).then((r) => { if (active) setData(r) }).catch((e) => { if (active) setError(e.message) })
    return () => { active = false }
  }, [query])
  return <><h2>Pedidos y cobros por periodo</h2>
    <form className="ops-form" onSubmit={(e) => { e.preventDefault(); setQuery(new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString()) }}>
      <label>Desde<input type="date" value={filters.desde} onChange={(e) => setFilters({ ...filters, desde: e.target.value })} /></label>
      <label>Hasta<input type="date" value={filters.hasta} onChange={(e) => setFilters({ ...filters, hasta: e.target.value })} /></label>
      <label>Estado<select value={filters.estado} onChange={(e) => setFilters({ ...filters, estado: e.target.value })}><option value="">Todos</option>{['recibido', 'en_preparacion', 'listo', 'entregado', 'pagado', 'anulado'].map((state) => <option key={state} value={state}>{state.replace('_', ' ')}</option>)}</select></label><button>Consultar</button>
    </form>{error && <p role="alert" className="ops-error">{error}</p>}
    {data && <><p role="status">{data.mensaje}</p><p>{data.criterio_fecha}</p>
      <div className="ops-grid"><p><strong>{data.totales.pedidos}</strong> pedidos · {cash(data.totales.importe_pedidos)}</p><p><strong>{data.totales.anulaciones}</strong> anulaciones · {cash(data.totales.importe_anulado)}</p><p><strong>{data.totales.pagos_registrados}</strong> pagos · {cash(data.totales.cobrado)}</p><p>Pendiente de cobro: <strong>{cash(data.totales.pendiente_cobro)}</strong></p></div>
      <a className="ops-link" href={`/api/admin/reports/export?${query}`}>Descargar operaciones CSV</a>
      <div className="ops-table-wrap" tabIndex={0}><table><caption>Pedidos incluidos</caption><thead><tr><th>Código</th><th>Creado</th><th>Estado</th><th>Total</th><th>Anulación</th></tr></thead><tbody>{data.pedidos.map((order) => <tr key={order.codigo}><td>{order.codigo}</td><td>{new Date(order.creado_en).toLocaleString('es-PE', { timeZone: 'America/Lima' })}</td><td>{order.estado}</td><td>{cash(order.total)}</td><td>{order.motivo_anulacion || '—'}</td></tr>)}</tbody></table></div>
      <div className="ops-table-wrap" tabIndex={0}><table><caption>Pagos registrados de estos pedidos</caption><thead><tr><th>Pedido</th><th>Registrado</th><th>Medio</th><th>Importe</th><th>Origen</th></tr></thead><tbody>{data.pagos.map((payment) => <tr key={payment.id}><td>{payment.codigo}</td><td>{new Date(payment.registrado_en).toLocaleString('es-PE', { timeZone: 'America/Lima' })}</td><td>{payment.metodo}</td><td>{cash(payment.importe)}</td><td>{payment.origen}</td></tr>)}</tbody></table></div>
    </>}
  </>
}
