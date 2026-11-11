import { useEffect, useState } from 'react'
import { apiJson } from './api.js'

export default function RecipeEditor() {
  const [recipes, setRecipes] = useState([])
  const [stock, setStock] = useState([])
  const [selected, setSelected] = useState('')
  const [parts, setParts] = useState([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    let active = true
    Promise.all([apiJson('/api/admin/recipes'), apiJson('/api/admin/inventory')]).then(([r, s]) => {
      if (active) { setRecipes(r.recetas); setStock(s.ingredientes) }
    }).catch((failure) => { if (active) setError(failure.message) })
    return () => { active = false }
  }, [])
  const recipe = recipes.find((row) => row.clave === selected)
  function choose(key) { setSelected(key); setParts(recipes.find((row) => row.clave === key)?.componentes || []); setNotice('') }
  function update(index, change) { setParts((current) => current.map((part, i) => i === index ? { ...part, ...change } : part)) }
  return <>
    <h2>Recetas de consumo</h2><p>Las cantidades iniciales son estimaciones ficticias para la demostración. Cada receta está identificada por producto o ingrediente y tamaño. Los pedidos conservan el plan utilizado al confirmarlos.</p>
    {error && <p role="alert" className="ops-error">{error}</p>}{notice && <p role="status">{notice}</p>}
    <label>Buscar receta<input type="search" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
    <label className="ops-selector">Producto o ingrediente<select value={selected} onChange={(e) => choose(e.target.value)}><option value="">Selecciona una receta</option>{recipes.filter((r) => r.clave === selected || r.nombre.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map((r) => <option key={r.clave} value={r.clave}>{r.nombre}</option>)}</select></label>
    {recipe && <form onSubmit={async (e) => {
      e.preventDefault(); setBusy(true); setError(''); setNotice('')
      try {
        const result = await apiJson(`/api/admin/recipes/${encodeURIComponent(selected)}`, { method: 'PUT', body: { componentes: parts.map((part) => ({ ...part, cantidad: Number(part.cantidad) })) } })
        setRecipes((current) => current.map((r) => r.clave === selected ? result.receta : r)); setParts(result.receta.componentes); setNotice('Receta guardada. Los pedidos nuevos utilizarán esta revisión.')
      } catch (failure) { setError(failure.message) } finally { setBusy(false) }
    }}>
      <p>Origen: {recipe.origen === 'estimacion_demo' ? 'Estimación de demostración' : 'Configurada por administración'} · Revisión {recipe.revision}</p>
      {parts.map((part, index) => <div key={index} className="ops-form">
        <label>Insumo<select required value={part.insumo_id} onChange={(e) => update(index, { insumo_id: e.target.value, unidad: stock.find((s) => s.item_id === e.target.value)?.unidad || 'kg' })}><option value="">Selecciona</option>{stock.map((s) => <option key={s.item_id} value={s.item_id}>{s.nombre} ({s.unidad})</option>)}</select></label>
        <label>Cantidad por porción<input required type="number" min="0.000001" step="any" value={part.cantidad} onChange={(e) => update(index, { cantidad: e.target.value })} /></label>
        <label>Unidad<select value={part.unidad} onChange={(e) => update(index, { unidad: e.target.value })}>{['kg', 'g', 'l', 'ml', 'unidad', 'paquete'].map((unit) => <option key={unit}>{unit}</option>)}</select></label>
        <button type="button" disabled={parts.length <= 1 || busy} onClick={() => setParts((current) => current.filter((_, i) => i !== index))}>Quitar insumo</button>
      </div>)}
      <div className="ops-actions"><button type="button" disabled={busy} onClick={() => setParts([...parts, { insumo_id: '', cantidad: '', unidad: 'kg' }])}>Añadir insumo</button><button disabled={busy}>{busy ? 'Guardando…' : 'Guardar receta'}</button></div>
    </form>}
  </>
}
