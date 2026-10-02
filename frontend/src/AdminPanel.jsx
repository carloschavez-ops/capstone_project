import { useEffect, useState } from 'react'
import { ArrowLeft, Check, Clock3, Plus, RefreshCw, Save } from 'lucide-react'
import './admin-orders.css'
import PizzaCreateForm from './PizzaCreateForm.jsx'

const UNITS = ['unidad', 'g', 'kg', 'ml', 'l', 'paquete']
const ORDER_STATES = {
  recibido: 'Recibido',
  en_preparacion: 'En preparación',
  listo: 'Listo',
  entregado: 'Entregado',
  pagado: 'Pagado',
}
const ORDER_ACTIONS = {
  en_preparacion: { estado: 'listo', label: 'Marcar lista' },
  listo: { estado: 'entregado', label: 'Confirmar entrega' },
  entregado: { estado: 'pagado', label: 'Registrar pago' },
}

function formatOrderDate(value) {
  return new Intl.DateTimeFormat('es-PE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export default function AdminPanel({ onBack, onPizzaCreated }) {
  const [inventory, setInventory] = useState({ categorias: [], ingredientes: [] })
  const [orders, setOrders] = useState([])
  const [activeTab, setActiveTab] = useState('pedidos')
  const [loading, setLoading] = useState(true)
  const [ordersLoading, setOrdersLoading] = useState(true)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const [newItem, setNewItem] = useState({ nombre: '', cantidad: '', unidad: 'kg', categoria: 'Otros' })
  const [adding, setAdding] = useState(false)
  const [pizzaFormOpen, setPizzaFormOpen] = useState(false)
  const [updatingCode, setUpdatingCode] = useState('')
  const hasReceivedOrders = orders.some((order) => order.estado === 'recibido')

  async function loadOrders() {
    setError('')
    try {
      const response = await fetch('/api/admin/orders')
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudieron cargar los pedidos.')
      setOrders(result.pedidos)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setOrdersLoading(false)
    }
  }

  async function loadInventory() {
    setError('')
    try {
      const response = await fetch('/api/admin/inventory')
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo cargar el inventario.')
      setInventory(result)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadOrders()
    const interval = window.setInterval(loadOrders, hasReceivedOrders ? 1000 : 5000)
    return () => window.clearInterval(interval)
  }, [hasReceivedOrders])

  useEffect(() => {
    if (activeTab === 'inventario') loadInventory()
  }, [activeTab])

  async function advanceOrder(order) {
    const action = ORDER_ACTIONS[order.estado]
    if (!action) return
    setUpdatingCode(order.codigo)
    setError('')
    try {
      const response = await fetch(`/api/admin/orders/${encodeURIComponent(order.codigo)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ estado: action.estado }),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo actualizar el pedido.')
      await loadOrders()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setUpdatingCode('')
    }
  }

  function updateRow(itemId, changes) {
    setInventory((current) => ({
      ...current,
      ingredientes: current.ingredientes.map((item) => item.item_id === itemId ? { ...item, ...changes } : item),
    }))
  }

  async function saveRow(item) {
    setError('')
    setSaved('')
    try {
      const response = await fetch(`/api/admin/inventory/ingrediente/${encodeURIComponent(item.item_id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cantidad: item.cantidad, unidad: item.unidad }),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo guardar la cantidad.')
      updateRow(item.item_id, result.item)
      setSaved(item.item_id)
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  async function addIngredient(event) {
    event.preventDefault()
    setAdding(true)
    setError('')
    try {
      const response = await fetch('/api/admin/inventory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...newItem, cantidad: Number(newItem.cantidad) }),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo agregar el insumo.')
      setInventory((current) => ({
        ...current,
        categorias: current.categorias.includes(result.item.categoria) ? current.categorias : [...current.categorias, result.item.categoria],
        ingredientes: [...current.ingredientes, result.item].sort((a, b) => a.nombre.localeCompare(b.nombre, 'es')),
      }))
      setNewItem({ nombre: '', cantidad: '', unidad: 'kg', categoria: result.item.categoria })
      setSaved(result.item.item_id)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setAdding(false)
    }
  }

  return (
    <section className="admin-page">
      <div className="admin-page-heading">
        <button className="admin-back" onClick={onBack}><ArrowLeft size={16} /> Volver a la carta</button>
        <p className="eyebrow">GESTIÓN DE COCINA</p>
        <h1>Panel admin<span>.</span></h1>
        <p>Pedidos, preparación y stock del local.</p>
        <button className="admin-add-pizza" onClick={() => setPizzaFormOpen(true)}><Plus size={16} /> Agregar pizza</button>
      </div>

      {error && <p className="admin-error" role="alert">{error}</p>}
      {saved && <p className="admin-saved" role="status"><Check size={15} /> Cambios guardados</p>}
      <div className="admin-tabs" role="tablist" aria-label="Administración">
        <button role="tab" aria-selected={activeTab === 'pedidos'} className={activeTab === 'pedidos' ? 'active' : ''} onClick={() => setActiveTab('pedidos')}>Pedidos <span>{orders.filter((order) => order.estado !== 'pagado').length}</span></button>
        <button role="tab" aria-selected={activeTab === 'inventario'} className={activeTab === 'inventario' ? 'active' : ''} onClick={() => setActiveTab('inventario')}>Inventario</button>
      </div>

      {activeTab === 'pedidos' ? (
        <section className="admin-orders-section" aria-label="Pedidos recibidos">
          <header className="admin-orders-heading">
            <div><p className="eyebrow">COCINA Y CAJA</p><h2>Pedidos</h2></div>
            <button className="orders-refresh" onClick={loadOrders} disabled={ordersLoading} aria-label="Actualizar pedidos" title="Actualizar pedidos"><RefreshCw size={16} /></button>
          </header>
          <p className="orders-estimate-note"><Clock3 size={14} /> Estimado orientativo: 8 minutos por pizza en la cola.</p>
          {ordersLoading ? <p className="admin-loading">Cargando pedidos...</p> : orders.length === 0 ? (
            <p className="orders-empty">Todavía no hay pedidos.</p>
          ) : (
            <div className="admin-order-list">
              {orders.map((order) => {
                const action = ORDER_ACTIONS[order.estado]
                const itemCount = order.items.reduce((sum, item) => sum + item.cantidad, 0)
                return (
                  <article className="admin-order" key={order.codigo}>
                    <div className="admin-order-top">
                      <div><strong className="admin-order-code">{order.codigo}</strong><time dateTime={order.creado_en}>{formatOrderDate(order.creado_en)}</time></div>
                      <span className={`order-status status-${order.estado}`}>{ORDER_STATES[order.estado] || order.estado}</span>
                    </div>
                    <div className="admin-order-customer">
                      <strong>{order.cliente}</strong><a href={`tel:${order.telefono}`}>{order.telefono}</a>
                      <span>{order.tipo_entrega === 'delivery' ? 'Delivery' : order.tipo_entrega === 'retiro_local' ? 'Retiro en local' : `Mesa ${order.numero_mesa}`}</span>
                    </div>
                    {order.tipo_entrega === 'delivery' && <p className="admin-order-address">{order.direccion}{order.referencia ? ` · ${order.referencia}` : ''}</p>}
                    <ul className="admin-order-items">
                      {order.items.map((item, index) => <li key={`${item.nombre}-${index}`}><span>{item.cantidad} × {item.nombre} <small>{item.tamano}</small></span><strong>S/ {Number(item.total).toFixed(2)}</strong></li>)}
                    </ul>
                    <div className="admin-order-bottom">
                      <div className="admin-order-total"><span>{itemCount} {itemCount === 1 ? 'artículo' : 'artículos'} · {order.metodo_pago}</span><strong>S/ {Number(order.total).toFixed(2)}</strong></div>
                      {order.estado === 'pagado' ? <span className="order-paid"><Check size={15} /> Pago registrado</span> : <div className="admin-order-controls">
                        {order.estimado_minutos !== null && <span className="order-eta"><Clock3 size={15} /> Salida estimada en ~{order.estimado_minutos} min</span>}
                        {order.estado === 'recibido' && <span className="order-auto-start">Preparación automática en breve</span>}
                        {action && <button className="order-action" onClick={() => advanceOrder(order)} disabled={updatingCode === order.codigo}>{updatingCode === order.codigo ? 'Actualizando...' : action.label}</button>}
                      </div>}
                    </div>
                  </article>
                )
              })}
            </div>
          )}
          <p className="orders-payment-note">“Registrar pago” confirma el cobro realizado en caja; no procesa pagos en línea.</p>
        </section>
      ) : loading ? <p className="admin-loading">Cargando inventario...</p> : (
        <div className="inventory-sections">
          <section className="inventory-section">
            <header><div><p className="eyebrow">STOCK DEL LOCAL</p><h2>Inventario</h2></div><span>{inventory.ingredientes.length} insumos</span></header>
            <form className="new-inventory-form" onSubmit={addIngredient}>
              <label>Nuevo insumo<input required maxLength={120} placeholder="Nombre del insumo" value={newItem.nombre} onChange={(event) => setNewItem({ ...newItem, nombre: event.target.value })} /></label>
              <label>Categoría<select value={newItem.categoria} onChange={(event) => setNewItem({ ...newItem, categoria: event.target.value })}>{inventory.categorias.map((category) => <option key={category} value={category}>{category}</option>)}{!inventory.categorias.includes('Otros') && <option value="Otros">Otros</option>}</select></label>
              <label>Unidad<select value={newItem.unidad} onChange={(event) => setNewItem({ ...newItem, unidad: event.target.value })}>{UNITS.map((unit) => <option key={unit} value={unit}>{unit}</option>)}</select></label>
              <label>Cantidad inicial<input required type="number" min="0" step="any" value={newItem.cantidad} onChange={(event) => setNewItem({ ...newItem, cantidad: event.target.value })} /></label>
              <button className="primary-button" disabled={adding}><Plus size={16} /> Agregar insumo</button>
            </form>
          </section>
          {inventory.categorias.map((category) => {
            const items = inventory.ingredientes.filter((item) => item.categoria === category)
            if (!items.length) return null
            return <section className="inventory-section" key={category}>
              <header><div><p className="eyebrow">ALMACÉN</p><h2>{category}</h2></div><span>{items.length} insumos</span></header>
              <div className="inventory-labels"><span>Insumo</span><span>Existencias</span><span>Unidad</span><span></span></div>
              <div className="inventory-rows">
                {items.map((item) => (
                  <div className="inventory-row" key={item.item_id}>
                    <strong>{item.nombre}</strong>
                    <input aria-label={`Cantidad de ${item.nombre}`} type="number" min="0" step="any" value={item.cantidad} onChange={(event) => updateRow(item.item_id, { cantidad: event.target.value })} />
                    <select aria-label={`Unidad de ${item.nombre}`} value={item.unidad} onChange={(event) => updateRow(item.item_id, { unidad: event.target.value })}>{UNITS.map((unit) => <option key={unit} value={unit}>{unit}</option>)}</select>
                    <button className="save-stock" onClick={() => saveRow(item)} aria-label={`Guardar ${item.nombre}`} title="Guardar"><Save size={16} /></button>
                  </div>
                ))}
              </div>
            </section>
          })}
        </div>
      )}
      {pizzaFormOpen && <PizzaCreateForm onClose={() => setPizzaFormOpen(false)} onCreated={async () => {
        await onPizzaCreated()
        setSaved('Pizza agregada al catálogo')
      }} />}
    </section>
  )
}
