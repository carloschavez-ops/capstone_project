import { useEffect, useState } from 'react'
import { ArrowRight, ImagePlus, X } from 'lucide-react'

const TYPES = ['Italianas · 8 porciones', 'Personales', 'Familiares', 'Postre']

export default function PizzaCreateForm({ onClose, onCreated, mode = 'create', initialPizza = null }) {
  const isMenuProduct = mode === 'menu-edit'
  const [image, setImage] = useState(null)
  const [imagePreview, setImagePreview] = useState(initialPizza?.imagen || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [values, setValues] = useState(() => ({
    nombre: initialPizza?.nombre || '',
    descripcion: initialPizza?.descripcion || '',
    tipo: initialPizza?.subcategoria || TYPES[0],
    ingredientes: (initialPizza?.ingredientes || []).join('\n'),
    precio: initialPizza?.precio ?? initialPizza?.precios?.personal ?? '',
    precio_personal: initialPizza?.precios?.personal ?? '',
    precio_mediana: initialPizza?.precios?.mediana ?? '',
    precio_familiar: initialPizza?.precios?.familiar ?? '',
  }))

  useEffect(() => {
    if (!initialPizza) return
    setValues({
      nombre: initialPizza.nombre || '',
      descripcion: initialPizza.descripcion || '',
      tipo: initialPizza.subcategoria || TYPES[0],
      ingredientes: (initialPizza.ingredientes || []).join('\n'),
      precio: initialPizza.precio ?? initialPizza.precios?.personal ?? '',
      precio_personal: initialPizza.precios?.personal ?? '',
      precio_mediana: initialPizza.precios?.mediana ?? '',
      precio_familiar: initialPizza.precios?.familiar ?? '',
    })
    setImagePreview(initialPizza.imagen || '')
  }, [initialPizza])

  function selectImage(file) {
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setError('La imagen debe ser JPG, PNG o WEBP.')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('La imagen no puede superar 5 MB.')
      return
    }
    setImage(file)
    setImagePreview(URL.createObjectURL(file))
    setError('')
  }

  async function submit(event) {
    event.preventDefault()
    const form = new FormData()
    form.set('nombre', values.nombre)
    form.set('descripcion', values.descripcion)

    if (isMenuProduct) {
      form.set('precio', String(values.precio))
    } else {
      form.set('tipo', values.tipo)
      form.set('ingredientes', values.ingredientes)
      form.set('precio_personal', String(values.precio_personal))
      form.set('precio_mediana', String(values.precio_mediana))
      form.set('precio_familiar', String(values.precio_familiar))
    }

    if (image) {
      form.set('imagen', image)
    } else if (mode === 'edit' || mode === 'menu-edit') {
      if (initialPizza?.imagen) form.set('imagen', initialPizza.imagen)
    }

    setBusy(true)
    setError('')
    try {
      const isEditMode = mode === 'edit' || mode === 'menu-edit'
      const endpoint = isEditMode
        ? (isMenuProduct ? `/api/admin/menu-items/${encodeURIComponent(initialPizza.id)}` : `/api/admin/pizzas/${encodeURIComponent(initialPizza.id)}`)
        : '/api/admin/pizzas'
      const response = await fetch(endpoint, { method: isEditMode ? 'PUT' : 'POST', body: form })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo guardar el producto.')
      await onCreated(result.pizza || result.item)
      onClose()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="overlay" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="pizza-create-dialog" role="dialog" aria-modal="true" aria-labelledby="pizza-create-title">
        <div className="panel-top"><span className="eyebrow">{isMenuProduct ? 'EDITAR PRODUCTO' : mode === 'edit' ? 'EDITAR RECETA' : 'NUEVA RECETA'}</span><button className="icon-button" onClick={onClose} aria-label="Cerrar"><X size={19} /></button></div>
        <h2 id="pizza-create-title">{isMenuProduct ? 'Editar producto' : mode === 'edit' ? 'Editar pizza' : 'Agregar pizza'}</h2>
        <form className="pizza-create-form" onSubmit={submit}>
          <label>Nombre<input name="nombre" required maxLength={160} autoFocus value={values.nombre} onChange={(event) => setValues((current) => ({ ...current, nombre: event.target.value }))} /></label>
          <label>Descripción<textarea name="descripcion" rows="3" maxLength={2000} value={values.descripcion} onChange={(event) => setValues((current) => ({ ...current, descripcion: event.target.value }))} /></label>
          {!isMenuProduct && <label>Tipo de pizza<select name="tipo" required value={values.tipo} onChange={(event) => setValues((current) => ({ ...current, tipo: event.target.value }))}>{TYPES.map((type) => <option key={type} value={type}>{type}</option>)}</select></label>}
          {!isMenuProduct && <label>Ingredientes <span className="form-hint">Uno por línea</span><textarea name="ingredientes" rows="3" placeholder={'Salsa de tomate\nMozzarella\nAlbahaca'} value={values.ingredientes} onChange={(event) => setValues((current) => ({ ...current, ingredientes: event.target.value }))} /></label>}
          {isMenuProduct ? (
            <label>Precio<span className="price-input"><span>S/</span><input name="precio" type="number" min="0" step="0.1" required value={values.precio} onChange={(event) => setValues((current) => ({ ...current, precio: event.target.value }))} /></span></label>
          ) : (
            <div className="pizza-create-prices"><span>Precios por tamaño</span>{[['personal', 'Personal'], ['mediana', 'Mediana'], ['familiar', 'Familiar']].map(([key, label]) => <label key={key}>{label}<span className="price-input"><span>S/</span><input name={`precio_${key}`} type="number" min="0.1" step="0.1" required value={values[`precio_${key}`]} onChange={(event) => setValues((current) => ({ ...current, [`precio_${key}`]: event.target.value }))} /></span></label>)}</div>
          )}
          <label className="pizza-image-field">Imagen referencial<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => selectImage(event.target.files?.[0])} /><span className="image-file-name">{image ? image.name : imagePreview ? <span>Imagen actual</span> : <><ImagePlus size={15} /> Subir JPG, PNG o WEBP · Máx. 5 MB</>}</span></label>
          {imagePreview && <img className="pizza-create-preview" src={imagePreview} alt="Vista previa del producto" />}
          {error && <p className="admin-error" role="alert">{error}</p>}
          <button className="primary-button" disabled={busy}>{busy ? 'Guardando...' : isMenuProduct ? 'Actualizar cambios' : mode === 'edit' ? 'Actualizar cambios' : 'Agregar al catálogo'} <ArrowRight size={16} /></button>
        </form>
      </section>
    </div>
  )
}
