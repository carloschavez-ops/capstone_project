import { useEffect, useState } from 'react'
import { ArrowDown, ArrowRight, Check, ChefHat, ChevronDown, CirclePlus, Clock3, Minus, Plus, ShoppingBag, X } from 'lucide-react'

const money = (value) => `S/ ${Number(value || 0).toFixed(2)}`
const readCart = () => {
  try {
    return JSON.parse(localStorage.getItem('pizza-pronto-cart') || '[]')
  } catch {
    return []
  }
}

export default function App() {
  const [catalog, setCatalog] = useState(null)
  const [catalogError, setCatalogError] = useState('')
  const [category, setCategory] = useState('Todas')
  const [cart, setCart] = useState(readCart)
  const [cartOpen, setCartOpen] = useState(false)
  const [builder, setBuilder] = useState(null)
  const [size, setSize] = useState('mediana')
  const [ingredients, setIngredients] = useState([])
  const [quote, setQuote] = useState(null)
  const [quoteError, setQuoteError] = useState('')
  const [checkout, setCheckout] = useState(false)
  const [customer, setCustomer] = useState({ nombre: '', telefono: '', tipo_entrega: 'domicilio', direccion: '' })
  const [payment, setPayment] = useState('efectivo')
  const [order, setOrder] = useState(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    fetch('/api/catalog')
      .then(async (response) => {
        if (!response.ok) throw new Error('No se pudo conectar con el backend.')
        return response.json()
      })
      .then(setCatalog)
      .catch((error) => setCatalogError(error.message))
  }, [])

  useEffect(() => {
    localStorage.setItem('pizza-pronto-cart', JSON.stringify(cart))
  }, [cart])

  useEffect(() => {
    if (!builder || !catalog) return
    let active = true
    setQuoteError('')
    fetch('/api/quote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pizza_id: builder.id || null, tamano_id: size, ingredientes: ingredients }),
    })
      .then(async (response) => {
        const result = await response.json()
        if (!response.ok && response.status !== 422) throw new Error(result.error || 'No se pudo calcular el precio.')
        return result
      })
      .then((result) => active && setQuote(result))
      .catch((error) => active && setQuoteError(error.message))
    return () => { active = false }
  }, [builder, size, ingredients, catalog])

  const categories = ['Todas', ...new Set((catalog?.pizzas || []).map((pizza) => pizza.categoria))]
  const pizzas = category === 'Todas'
    ? catalog?.pizzas || []
    : (catalog?.pizzas || []).filter((pizza) => pizza.categoria === category)
  const units = cart.reduce((sum, item) => sum + item.cantidad, 0)
  const subtotal = cart.reduce((sum, item) => sum + item.precio_unitario * item.cantidad, 0)
  const delivery = subtotal >= (catalog?.delivery.gratis_desde || 60) || subtotal === 0 ? 0 : (catalog?.delivery.costo || 5)

  function openBuilder(pizza = null) {
    setBuilder(pizza || { id: '', nombre: 'Pizza a tu manera', descripcion: 'Empieza con una base y termina con tus ingredientes favoritos.' })
    setSize('mediana')
    setIngredients(pizza ? [...pizza.ingredientes] : ['masa_clasica', 'salsa_tomate', 'mozzarella'])
    setQuote(null)
    setQuoteError('')
  }

  function addConfiguredPizza() {
    if (!quote?.ok || !builder) return
    const item = {
      key: `${Date.now()}-${Math.random()}`,
      pizza_id: builder.id || null,
      nombre: builder.nombre,
      tamano_id: size,
      ingredientes: [...ingredients],
      cantidad: 1,
      precio_unitario: quote.total,
      detalle: quote.detalle,
    }
    setCart((previous) => [...previous, item])
    setBuilder(null)
    setNotice('Pizza añadida al pedido')
    window.setTimeout(() => setNotice(''), 2600)
  }

  function changeQuantity(key, amount) {
    setCart((previous) => previous
      .map((item) => item.key === key ? { ...item, cantidad: Math.max(0, Math.min(20, item.cantidad + amount)) } : item)
      .filter((item) => item.cantidad > 0))
  }

  async function placeOrder(event) {
    event.preventDefault()
    setBusy(true)
    setNotice('')
    try {
      const response = await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cliente: customer, metodo_pago: payment, items: cart }),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No pudimos registrar tu pedido.')
      setOrder(result.pedido)
      setCart([])
      setCheckout(false)
    } catch (error) {
      setNotice(error.message)
    } finally {
      setBusy(false)
    }
  }

  const ingredientGroups = catalog?.grupos || []

  return (
    <>
      <header className="site-header">
        <a className="brand" href="#inicio" aria-label="Pizza Pronto, inicio"><span className="brand-mark">P</span><span>pizza<span className="brand-light">pronto</span></span></a>
        <nav className="main-nav" aria-label="Navegación principal"><a href="#carta">La carta</a><a href="#nosotros">Nuestra cocina</a></nav>
        <button className="cart-trigger" onClick={() => { setCartOpen(true); setCheckout(false) }} aria-label={`Abrir pedido, ${units} productos`}><ShoppingBag size={18} /><span>Tu pedido</span><b>{units}</b></button>
      </header>

      <main id="inicio">
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow"><span className="live-dot" /> HORNO ENCENDIDO · LIMA</p>
            <h1>Una buena pizza<br />siempre <em>reúne.</em></h1>
            <p className="hero-subtitle">Masa lenta, ingredientes honestos y ese primer trozo que nadie quiere soltar.</p>
            <a className="hero-link" href="#carta">Encuentra tu favorita <ArrowDown size={16} /></a>
            <div className="hero-note"><span>01</span><span>Hechas al momento<br />desde 1998</span></div>
          </div>
          <div className="hero-art" role="img" aria-label="Pizza artesanal recién salida del horno">
            <div className="hero-stamp"><span>HECHA</span><strong>con calma</strong><span>COMPARTIDA CON GANAS</span></div>
            <span className="hero-spark">✳</span>
            <span className="hero-caption">Nápoles, con un giro nuestro.</span>
          </div>
          <div className="hero-bottom"><span>BUENAS COSAS, SIN PRISA</span><span>01 — 07 / CARTA DE LA CASA</span></div>
        </section>

        <section className="menu-section" id="carta">
          <div className="section-heading"><div><p className="eyebrow">EL MENÚ</p><h2>Sale del horno,<br /><em>va a tu mesa.</em></h2></div><p className="section-intro">Recetas con carácter, bordes dorados y productos de temporada. Elige una de la casa o hazla a tu manera.</p></div>
          <div className="menu-toolbar"><div className="category-tabs" role="tablist" aria-label="Filtrar por categoría">{categories.map((item) => <button key={item} className={category === item ? 'active' : ''} onClick={() => setCategory(item)} role="tab" aria-selected={category === item}>{item === 'Todas' ? item : item.replaceAll('_', ' ')}</button>)}</div><span className="menu-count">{pizzas.length.toString().padStart(2, '0')} PIZZAS</span></div>
          {catalogError ? <div className="empty-state"><strong>No logramos conectar con cocina.</strong><span>{catalogError} Inicia el backend y vuelve a cargar.</span></div> : !catalog ? <div className="loading-state">Encendiendo el horno...</div> : (
            <div className="pizza-grid">
              {pizzas.map((pizza, index) => <article className={`pizza-card tone-${index % 4}`} key={pizza.id}>
                <div className="pizza-image" style={pizza.imagen ? { backgroundImage: `url(${pizza.imagen})` } : undefined}>
                  {pizza.badge && <span className="pizza-badge">{pizza.badge}</span>}
                  {!pizza.imagen && <div className="pizza-illustration"><span>🍕</span><i>{String(index + 1).padStart(2, '0')}</i></div>}
                  <span className="pizza-category">{pizza.categoria.replaceAll('_', ' ')}</span>
                </div>
                <div className="pizza-info"><div className="pizza-title-row"><h3>{pizza.nombre}</h3><span>{money(pizza.precios.personal)}</span></div><p>{pizza.descripcion}</p><div className="pizza-foot"><span><Clock3 size={14} />{pizza.meta.replace('Lista en ', '')}</span><button onClick={() => openBuilder(pizza)} aria-label={`Personalizar ${pizza.nombre}`} title="Personalizar"><CirclePlus size={19} /><span>Elegir</span></button></div></div>
              </article>)}
            </div>
          )}
          <button className="custom-pizza" onClick={() => openBuilder()}><span className="custom-icon"><ChefHat size={22} /></span><span><b>¿Tienes una idea mejor?</b><small>Arma una pizza desde cero</small></span><ArrowRight size={19} /></button>
        </section>

        <section className="kitchen-band" id="nosotros"><div className="kitchen-number">02 <span>/ LA COCINA</span></div><div><p className="eyebrow">EL TIEMPO TAMBIÉN ES INGREDIENTE</p><h2>Fermentamos lento.<br /><em>Servimos caliente.</em></h2></div><p>Harina, agua, sal y paciencia. Nuestra masa descansa 48 horas antes de encontrarse con el fuego.</p><a href="#carta" aria-label="Volver al menú"><ArrowRight size={19} /></a></section>
      </main>

      <footer className="site-footer"><a className="brand" href="#inicio"><span className="brand-mark">P</span><span>pizza<span className="brand-light">pronto</span></span></a><span>BUENAS PIZZAS, BUENAS CONVERSACIONES.</span><span>LIMA · PERÚ © 2025</span></footer>

      {notice && <div className="toast" role="status">{notice}</div>}

      {builder && <div className="overlay" onMouseDown={(event) => event.target === event.currentTarget && setBuilder(null)}><section className="builder-panel" role="dialog" aria-modal="true" aria-labelledby="builder-title"><div className="panel-top"><span className="eyebrow">TU PIZZA, TUS REGLAS</span><button className="icon-button" onClick={() => setBuilder(null)} aria-label="Cerrar"><X size={20} /></button></div><h2 id="builder-title">{builder.nombre}</h2><p className="builder-description">{builder.descripcion}</p><label className="field-label" htmlFor="size">Tamaño</label><div className="size-options" id="size">{catalog?.tamanos.map((item) => <button key={item.id} className={size === item.id ? 'selected' : ''} onClick={() => setSize(item.id)}><span>{item.nombre.split(' ')[0]}</span><small>{item.nombre.match(/\d+ cm/)?.[0]} · {item.desc.split('·')[1]}</small></button>)}</div>
          <div className="ingredient-head"><label className="field-label">Ingredientes</label><span>Elige masa y salsa</span></div><div className="ingredient-list">{ingredientGroups.map((group) => <fieldset className="ingredient-group" key={group.id}><legend>{group.nombre}<small>{group.ayuda}</small></legend><div className="ingredient-options">{catalog.ingredientes.filter((item) => item.grupo === group.id).map((item) => { const selected = ingredients.includes(item.id); const blocked = quote?.bloqueados?.[item.id]; return <button key={item.id} className={`ingredient-option ${selected ? 'chosen' : ''}`} disabled={Boolean(blocked)} title={blocked || item.nombre} onClick={() => setIngredients((current) => selected ? current.filter((id) => id !== item.id) : [...current, item.id])}><span className="ingredient-emoji">{item.emoji}</span><span>{item.nombre}</span><small>{Number(item.precio) === 0 ? 'Incluido' : `+${money(item.precio)}`}</small>{selected && <Check className="ingredient-check" size={15} />}</button>})}</div></fieldset>)}</div>
          {quote?.errores?.length > 0 && <p className="form-error">{quote.errores[0].detalle}</p>}{quoteError && <p className="form-error">{quoteError}</p>}
          <div className="builder-bottom"><div><small>PRECIO</small><strong>{quote ? money(quote.total) : '...'}</strong></div><button className="primary-button" disabled={!quote?.ok} onClick={addConfiguredPizza}>Añadir al pedido <ArrowRight size={17} /></button></div>
        </section></div>}

      {cartOpen && <div className="overlay" onMouseDown={(event) => event.target === event.currentTarget && setCartOpen(false)}><aside className="cart-panel" role="dialog" aria-modal="true" aria-labelledby="cart-title"><div className="panel-top"><span className="eyebrow">{checkout ? 'CASI EN TU MESA' : 'TU SELECCIÓN'}</span><button className="icon-button" onClick={() => setCartOpen(false)} aria-label="Cerrar pedido"><X size={20} /></button></div><h2 id="cart-title">{checkout ? 'Datos de entrega' : 'El pedido.'}</h2>
          {!checkout ? <>{cart.length === 0 ? <div className="cart-empty"><span>🍕</span><strong>La caja está vacía.</strong><p>Una pizza recién salida del horno podría cambiar eso.</p><button className="text-button" onClick={() => setCartOpen(false)}>Volver a la carta <ArrowRight size={16} /></button></div> : <><div className="cart-items">{cart.map((item) => <article className="cart-item" key={item.key}><div className="cart-item-icon">🍕</div><div className="cart-item-copy"><strong>{item.nombre}</strong><span>{catalog?.tamanos.find((t) => t.id === item.tamano_id)?.nombre} · {item.detalle.map((detail) => detail.nombre).join(', ')}</span><b>{money(item.precio_unitario)}</b></div><div className="quantity-control"><button onClick={() => changeQuantity(item.key, -1)} aria-label="Quitar una"><Minus size={13} /></button><span>{item.cantidad}</span><button onClick={() => changeQuantity(item.key, 1)} aria-label="Añadir una"><Plus size={13} /></button></div></article>)}</div><div className="cart-totals"><div><span>Subtotal</span><b>{money(subtotal)}</b></div><div><span>Envío {subtotal >= 60 ? '· Gratis' : ''}</span><b>{delivery ? money(delivery) : 'Gratis'}</b></div><div className="total-line"><span>Total</span><b>{money(subtotal + delivery)}</b></div></div><button className="primary-button checkout-button" disabled={!cart.length} onClick={() => setCheckout(true)}>Continuar con el pedido <ArrowRight size={17} /></button></> : <form className="checkout-form" onSubmit={placeOrder}><label>Nombre completo<input required autoComplete="name" value={customer.nombre} onChange={(event) => setCustomer({ ...customer, nombre: event.target.value })} /></label><label>Teléfono<input required autoComplete="tel" inputMode="tel" value={customer.telefono} onChange={(event) => setCustomer({ ...customer, telefono: event.target.value })} /></label><label>¿Cómo recibes tu pedido?<span className="select-wrap"><select value={customer.tipo_entrega} onChange={(event) => setCustomer({ ...customer, tipo_entrega: event.target.value })}><option value="domicilio">A domicilio</option><option value="recojo">Recojo en tienda</option></select><ChevronDown size={16} /></span></label>{customer.tipo_entrega === 'domicilio' && <label>Dirección<input required autoComplete="street-address" value={customer.direccion} onChange={(event) => setCustomer({ ...customer, direccion: event.target.value })} /></label>}<label>Método de pago<span className="select-wrap"><select value={payment} onChange={(event) => setPayment(event.target.value)}><option value="efectivo">Efectivo</option><option value="tarjeta">Tarjeta al recibir</option><option value="yape">Yape</option></select><ChevronDown size={16} /></span></label><div className="checkout-total"><span>Total del pedido</span><strong>{money(subtotal + delivery)}</strong></div>{notice && <p className="form-error">{notice}</p>}<button className="primary-button checkout-button" disabled={busy}>{busy ? 'Registrando...' : 'Confirmar pedido'} <ArrowRight size={17} /></button><button type="button" className="back-button" onClick={() => { setCheckout(false); setNotice('') }}>Volver al carrito</button></form>}
        </aside></div>}

      {order && <div className="overlay confirmation-overlay"><section className="confirmation-dialog" role="dialog" aria-modal="true" aria-labelledby="confirmation-title"><span className="confirmation-check"><Check size={24} /></span><p className="eyebrow">YA ESTÁ EN EL HORNO</p><h2 id="confirmation-title">¡Gracias, {order.cliente}!</h2><p>Recibimos tu pedido y cocina ya está trabajando en él.</p><div className="order-code"><span>CÓDIGO DE PEDIDO</span><strong>{order.codigo}</strong></div><div className="order-total"><span>Total · {order.items.reduce((total, item) => total + item.cantidad, 0)} pizzas</span><strong>{money(order.total)}</strong></div><button className="primary-button" onClick={() => { setOrder(null); setCartOpen(false) }}>Volver a la carta <ArrowRight size={17} /></button></section></div>}
    </>
  )
}