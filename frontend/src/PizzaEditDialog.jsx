import { useEffect, useState } from 'react'
import { ArrowRight, X } from 'lucide-react'

export default function PizzaEditDialog({ pizza, onClose, onSave }) {
  const [form, setForm] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setForm({
      nombre: pizza.nombre,
      descripcion: pizza.descripcion || '',
      precios: { ...pizza.precios },
    })
  }, [pizza])

  if (!form) return null

  function updatePrice(size, value) {
    setForm((current) => ({ ...current, precios: { ...current.precios, [size]: value } }))
  }

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await onSave(pizza.id, {
        ...form,
        precios: Object.fromEntries(Object.entries(form.precios).map(([key, value]) => [key, Number(value)])),
      })
      onClose()
    } catch (saveError) {
      setError(saveError.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="overlay" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="pizza-edit-dialog" role="dialog" aria-modal="true" aria-labelledby="pizza-edit-title">
        <div className="panel-top"><span className="eyebrow">EDITAR RECETA</span><button className="icon-button" onClick={onClose} aria-label="Cerrar"><X size={19} /></button></div>
        <h2 id="pizza-edit-title">Editar pizza</h2>
        <form className="pizza-edit-form" onSubmit={submit}>
          <label>Nombre<input required maxLength={120} value={form.nombre} onChange={(event) => setForm({ ...form, nombre: event.target.value })} /></label>
          <label>Descripción<textarea rows="3" value={form.descripcion} onChange={(event) => setForm({ ...form, descripcion: event.target.value })} /></label>
          <fieldset><legend>Precios por tamaño</legend>
            {[['personal', 'Personal'], ['mediana', 'Mediana'], ['familiar', 'Familiar']].map(([size, label]) => <label key={size}>{label}<span className="price-input"><span>S/</span><input type="number" min="0" step="0.5" required value={form.precios[size]} onChange={(event) => updatePrice(size, event.target.value)} /></span></label>)}
          </fieldset>
          {error && <p className="admin-error" role="alert">{error}</p>}
          <button className="primary-button" disabled={busy}>{busy ? 'Guardando...' : 'Guardar cambios'} <ArrowRight size={16} /></button>
        </form>
      </section>
    </div>
  )
}