import { useState } from 'react'
import { ArrowLeft, ArrowRight, Bike, Store, Utensils } from 'lucide-react'

const STORE_ADDRESS = 'Av. Manco Cápac 618, Cajamarca 06004'
const DELIVERY_OPTIONS = [
  { id: 'delivery', label: 'Delivery', icon: Bike },
  { id: 'retiro_local', label: 'Retiro local', icon: Store },
  { id: 'comer_local', label: 'Comer en local', icon: Utensils },
]

export default function GuestEntryForm({ onSubmit, onBack, busy, error }) {
  const [customer, setCustomer] = useState({
    nombre: '',
    telefono: '',
    tipo_entrega: 'delivery',
    direccion: '',
    referencia: '',
    dni_ruc: '',
    numero_mesa: '',
  })

  function update(field, value) {
    setCustomer((current) => ({ ...current, [field]: value }))
  }

  function submit(event) {
    event.preventDefault()
    onSubmit(customer)
  }

  return (
    <main className="guest-entry-shell">
      <section className="guest-entry-story">
        <a className="brand guest-entry-brand" href="#inicio" aria-label="Pizza Pronto">
          <span className="brand-mark">P</span><span>pizza<span className="brand-light">pronto</span></span>
        </a>
        <div className="guest-entry-story-copy">
          <p className="eyebrow">TU PEDIDO, A TU RITMO</p>
          <h1>¿Dónde nos<br />encontramos?</h1>
          <p>Déjanos estos datos para preparar tu pedido como te gusta.</p>
        </div>
        <span className="guest-entry-caption">HECHA CON CALMA · SERVIDA CALIENTE</span>
      </section>

      <section className="guest-entry-side">
        <button className="guest-entry-back" onClick={onBack}><ArrowLeft size={16} /> Volver al acceso</button>
        <div className="guest-entry-box">
          <p className="eyebrow">CONTINUAR COMO INVITADO</p>
          <h2>Datos de entrega.</h2>
          <form className="guest-entry-form" onSubmit={submit}>
            <label>Nombre completo<input autoComplete="name" required maxLength={120} value={customer.nombre} onChange={(event) => update('nombre', event.target.value)} /></label>
            <label>Número de teléfono<input autoComplete="tel" type="tel" inputMode="tel" required maxLength={40} value={customer.telefono} onChange={(event) => update('telefono', event.target.value)} /></label>

            <fieldset className="delivery-choice">
              <legend>¿Cómo recibes tu pedido?</legend>
              <div className="delivery-options" role="radiogroup" aria-label="Modalidad del pedido">
                {DELIVERY_OPTIONS.map(({ id, label, icon: Icon }) => (
                  <button key={id} type="button" role="radio" aria-checked={customer.tipo_entrega === id} className={customer.tipo_entrega === id ? 'selected' : ''} onClick={() => update('tipo_entrega', id)}>
                    <Icon size={17} /><span>{label}</span>
                  </button>
                ))}
              </div>
            </fieldset>

            {customer.tipo_entrega === 'delivery' && <div className="guest-mode-fields">
              <label>Dirección<input autoComplete="street-address" required value={customer.direccion} onChange={(event) => update('direccion', event.target.value)} /></label>
              <label>Referencia<input required placeholder="Ej. Frente al parque" value={customer.referencia} onChange={(event) => update('referencia', event.target.value)} /></label>
              <label>DNI o RUC <span className="optional-label">Opcional</span><input inputMode="numeric" value={customer.dni_ruc} onChange={(event) => update('dni_ruc', event.target.value)} /></label>
            </div>}

            {customer.tipo_entrega === 'retiro_local' && <div className="guest-store-address"><Store size={17} /><span><small>RETIRO EN LOCAL</small><strong>{STORE_ADDRESS}</strong></span></div>}

            {customer.tipo_entrega === 'comer_local' && <div className="guest-mode-fields">
              <div className="guest-store-address"><Store size={17} /><span><small>TE ESPERAMOS EN</small><strong>{STORE_ADDRESS}</strong></span></div>
              <label>Número de mesa<input required inputMode="numeric" value={customer.numero_mesa} onChange={(event) => update('numero_mesa', event.target.value)} /></label>
              <label>DNI o RUC para la boleta<input required inputMode="numeric" value={customer.dni_ruc} onChange={(event) => update('dni_ruc', event.target.value)} /></label>
            </div>}

            {error && <p className="auth-error" role="alert">{error}</p>}
            <button className="primary-button guest-entry-submit" disabled={busy}>{busy ? 'Guardando...' : 'Ver la carta'} <ArrowRight size={17} /></button>
          </form>
        </div>
        <p className="guest-entry-footnote">BAÑOS DEL INCA · CAJAMARCA</p>
      </section>
    </main>
  )
}