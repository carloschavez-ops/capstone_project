import { useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowRight, Banknote, Check, ChefHat, ChevronDown, CirclePlus, Clock3, CreditCard, Eye, EyeOff, Facebook, Instagram, LogOut, MapPin, Minus, Pencil, Phone, Plus, Search, ShoppingBag, Smartphone, Trash2, Video, X } from 'lucide-react'
import AuthScreen from './AuthScreen.jsx'
import GuestEntryForm from './GuestEntryForm.jsx'
import AdminPanel from './AdminPanel.jsx'
import PizzaEditDialog from './PizzaEditDialog.jsx'
import PizzaCreateForm from './PizzaCreateForm.jsx'
import { ProductVisual } from './CategoryPlaceholder.jsx'
import brandLogo from './assets/logo-pala.png'
import './menu-catalog.css'
import './brand-footer.css'

const money = (value) => `S/ ${Number(value || 0).toFixed(2)}`
const readCart = () => {
  try {
    return JSON.parse(localStorage.getItem('pizza-pronto-cart') || '[]')
  } catch {
    return []
  }
}

export default function App() {
  const [user, setUser] = useState(null)
  const [authReady, setAuthReady] = useState(false)
  const [authMode, setAuthMode] = useState('login')
  const [authBusy, setAuthBusy] = useState(false)
  const [authError, setAuthError] = useState('')
  const [adminPanelOpen, setAdminPanelOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [catalog, setCatalog] = useState(null)
  const [catalogError, setCatalogError] = useState('')
  const [category, setCategory] = useState('Todas')
  const [menuSearch, setMenuSearch] = useState('')
  const [menuPizzaSizes, setMenuPizzaSizes] = useState({})
  const [cart, setCart] = useState(readCart)
  const [cartOpen, setCartOpen] = useState(false)
  const [builder, setBuilder] = useState(null)
  const [size, setSize] = useState('mediana')
  const [ingredients, setIngredients] = useState([])
  const [quote, setQuote] = useState(null)
  const [quoteError, setQuoteError] = useState('')
  const [checkout, setCheckout] = useState(false)
  const [customer, setCustomer] = useState({ nombre: '', telefono: '', tipo_entrega: 'delivery', direccion: '', referencia: '', dni_ruc: '', numero_mesa: '' })
  const [payment, setPayment] = useState('efectivo')
  const [cashTendered, setCashTendered] = useState('')
  const [addingPizza, setAddingPizza] = useState(false)
  const [order, setOrder] = useState(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [customBaseId, setCustomBaseId] = useState('')
  const noticeTimer = useRef(null)

  useEffect(() => {
    let active = true
    fetch('/api/auth/me')
      .then((response) => response.json())
      .then((result) => {
        if (!active) return
        if (result.authenticated) {
          setUser(result.user)
          if (result.mode === 'account') setCustomer((current) => ({ ...current, nombre: result.user.nombre }))
          if (result.mode === 'guest' && result.cliente) setCustomer(result.cliente)
        }
        setAuthReady(true)
      })
      .catch(() => {
        if (!active) return
        setAuthError('No se pudo conectar con el servidor. Intenta de nuevo.')
        setAuthReady(true)
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    const endpoint = user?.rol === 'admin' ? '/api/admin/catalog' : '/api/catalog'
    fetch(endpoint)
      .then(async (response) => {
        if (!response.ok) throw new Error('No se pudo conectar con el backend.')
        return response.json()
      })
      .then((result) => active && setCatalog((current) => ({ ...current, ...result })))
      .catch((error) => active && setCatalogError(error.message))
    return () => { active = false }
  }, [user])

  useEffect(() => {
    localStorage.setItem('pizza-pronto-cart', JSON.stringify(cart))
  }, [cart])

  useEffect(() => () => window.clearTimeout(noticeTimer.current), [])

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

  const menuItems = catalog?.menu_items || []
  const menuCategories = [...new Set(menuItems.map((item) => item.categoria))]
  const categories = ['Todas', ...menuCategories]
  const products = menuItems.filter((item) => user?.rol === 'admin' || item.activo)
  const normalizedSearch = menuSearch.trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase()
  const searchedProducts = normalizedSearch ? products.filter((item) => [item.nombre, item.categoria, item.subcategoria, item.descripcion, ...item.ingredientes].filter(Boolean).join(' ').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().includes(normalizedSearch)) : products
  const productGroups = (category === 'Todas' ? menuCategories : [category])
    .map((name) => ({ name, items: searchedProducts.filter((item) => item.categoria === name) }))
    .filter((group) => group.items.length > 0)
  const units = cart.reduce((sum, item) => sum + item.cantidad, 0)
  const subtotal = cart.reduce((sum, item) => sum + item.precio_unitario * item.cantidad, 0)
  const delivery = customer.tipo_entrega !== 'delivery' || subtotal >= (catalog?.delivery?.gratis_desde || 60) || subtotal === 0 ? 0 : (catalog?.delivery?.costo || 5)
  const orderTotal = subtotal + delivery
  const cashChange = cashTendered === '' ? null : Number(cashTendered) - orderTotal
  const availablePizzas = (catalog?.pizzas || []).filter((pizza) => pizza.activo)

  function showNotice(message, duration = 2600) {
    window.clearTimeout(noticeTimer.current)
    setNotice(message)
    noticeTimer.current = window.setTimeout(() => setNotice(''), duration)
  }

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
    showNotice('Pizza añadida al pedido')
  }

  function addMenuItem(item) {
    const sizeId = item.precios ? (menuPizzaSizes[item.id] || 'personal') : null
    const price = sizeId ? item.precios[sizeId] : item.precio
    setCart((previous) => [...previous, {
      key: `${Date.now()}-${Math.random()}`,
      menu_item_id: item.id,
      nombre: item.nombre,
      categoria: item.categoria,
      subcategoria: item.subcategoria,
      tamano_id: sizeId,
      descripcion: item.descripcion,
      imagen: item.imagen,
      ingredientes: [...item.ingredientes],
      detalle: item.ingredientes.map((nombre) => ({ nombre })),
      es_pizza: item.es_pizza,
      cantidad: 1,
      precio_unitario: price,
    }])
    showNotice(`${item.nombre} agregado al pedido`)
  }

  async function choosePizza(pizza) {
    setAddingPizza(true)
    try {
      const response = await fetch('/api/quote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pizza_id: pizza.id, tamano_id: 'personal', ingredientes: pizza.ingredientes }),
      })
      const result = await response.json()
      if (!response.ok || !result.ok) throw new Error(result.errores?.[0]?.detalle || result.error || 'No se pudo agregar esta pizza.')
      setCart((previous) => [...previous, {
        key: `${Date.now()}-${Math.random()}`,
        pizza_id: pizza.id,
        nombre: pizza.nombre,
        tamano_id: 'personal',
        ingredientes: [...pizza.ingredientes],
        cantidad: 1,
        precio_unitario: result.total,
        detalle: result.detalle,
      }])
      showNotice(`${pizza.nombre} añadida al pedido`)
    } catch (error) {
      showNotice(error.message)
    } finally {
      setAddingPizza(false)
    }
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
        body: JSON.stringify({
          cliente: customer,
          metodo_pago: payment,
          paga_con: payment === 'efectivo' ? Number(cashTendered) : null,
          items: cart,
        }),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No pudimos registrar tu pedido.')
      setOrder(result.pedido)
      setCart([])
      setCheckout(false)
      setCashTendered('')
    } catch (error) {
      setNotice(error.message)
    } finally {
      setBusy(false)
    }
  }

  const ingredientGroups = catalog?.grupos || []

  async function authenticate(mode, values = {}) {
    setAuthBusy(true)
    setAuthError('')
    const endpoint = mode === 'guest' ? '/api/auth/guest' : `/api/auth/${mode}`
    const payload = mode === 'guest' ? { cliente: values.cliente } : {
      nombre: values.nombre,
      email: values.email,
      password: values.password,
    }
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo iniciar la sesión.')
      setUser(result.user)
      if (result.mode === 'guest') setCustomer(result.cliente)
      if (result.mode === 'account') setCustomer((current) => ({ ...current, nombre: result.user.nombre }))
    } catch (error) {
      setAuthError(error.message)
    } finally {
      setAuthBusy(false)
    }
  }

  async function logout() {
    try {
      await fetch('/api/auth/logout', { method: 'POST' })
    } finally {
      setUser(null)
      setCart([])
      setCustomer({ nombre: '', telefono: '', tipo_entrega: 'delivery', direccion: '', referencia: '', dni_ruc: '', numero_mesa: '' })
      setCheckout(false)
      setAuthMode('login')
      setAdminPanelOpen(false)
    }
  }

  async function refreshAdminCatalog() {
    const response = await fetch('/api/admin/catalog')
    const result = await response.json()
    if (!response.ok) throw new Error(result.error || 'No se pudo actualizar la carta.')
    setCatalog((current) => ({ ...current, ...result }))
  }

  async function savePizza(pizzaId, changes) {
    const response = await fetch(`/api/admin/pizzas/${encodeURIComponent(pizzaId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(changes),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.error || 'No se pudo editar la pizza.')
    await refreshAdminCatalog()
    showNotice('Pizza actualizada')
  }

  async function toggleMenuItemVisibility(item) {
    const endpoint = item.es_pizza ? `/api/admin/pizzas/${encodeURIComponent(item.id)}/visibility` : `/api/admin/menu-items/${encodeURIComponent(item.id)}/visibility`
    try {
      const response = await fetch(endpoint, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ activo: !item.activo }),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo cambiar la visibilidad.')
      await refreshAdminCatalog()
      showNotice(item.activo ? 'Producto ocultado de la carta' : 'Producto visible en la carta')
    } catch (error) {
      showNotice(error.message)
    }
  }

  async function deleteMenuItem(item) {
    if (!window.confirm(`¿Eliminar “${item.nombre}” de forma permanente?`)) return
    const endpoint = item.es_pizza ? `/api/admin/pizzas/${encodeURIComponent(item.id)}` : `/api/admin/menu-items/${encodeURIComponent(item.id)}`
    try {
      const response = await fetch(endpoint, { method: 'DELETE' })
      const result = await response.json()
      if (!response.ok) throw new Error(result.error || 'No se pudo eliminar el producto.')
      await refreshAdminCatalog()
      showNotice(item.es_pizza ? 'Pizza eliminada' : 'Producto eliminado', 10000)
    } catch (error) {
      showNotice(error.message)
    }
  }

  async function togglePizzaVisibility(pizza) {
    await toggleMenuItemVisibility(pizza)
  }

  async function deletePizza(pizza) {
    await deleteMenuItem(pizza)
  }

  if (!authReady) {
    return <main className="auth-loading"><span className="brand-mark">P</span><p>Preparando la mesa...</p></main>
  }

  if (!user) {
    if (authMode === 'guest') {
      return <GuestEntryForm
        onSubmit={(guestCustomer) => authenticate('guest', { cliente: guestCustomer })}
        onBack={() => { setAuthMode('login'); setAuthError('') }}
        busy={authBusy}
        error={authError}
      />
    }
    return <AuthScreen
      mode={authMode}
      onModeChange={(mode) => { setAuthMode(mode); setAuthError('') }}
      onSubmit={authenticate}
      onGuest={() => { setAuthMode('guest'); setAuthError('') }}
      busy={authBusy}
      error={authError}
    />
  }

  return (
    <>
      <header className="site-header">
        <a className="brand" href="#inicio" aria-label="Pizza Pronto Italiana, inicio"><img className="brand-logo" src={brandLogo} alt="" /><span className="brand-name">Pizza Pronto <span className="brand-italiana">Italiana</span></span></a>
        <nav className="main-nav" aria-label="Navegación principal"><button onClick={() => setAdminPanelOpen(false)}>La carta</button><a href="#nosotros">Nuestra cocina</a>{user.rol === 'admin' && <button className={adminPanelOpen ? 'nav-admin active' : 'nav-admin'} onClick={() => setAdminPanelOpen(true)}>Panel admin</button>}</nav>
        <div className="header-actions"><span className="user-greeting">Hola, {user.nombre}</span><button className="logout-button" onClick={logout} aria-label="Cerrar sesión" title="Cerrar sesión"><LogOut size={17} /><span>Salir</span></button><button className="cart-trigger" onClick={() => { setCartOpen(true); setCheckout(false) }} aria-label={`Abrir pedido, ${units} ${units === 1 ? 'producto' : 'productos'}`}><ShoppingBag size={18} /><span>Tu pedido</span><b>{units}</b></button></div>
      </header>

      <main id="inicio">
        {adminPanelOpen ? <AdminPanel onBack={() => setAdminPanelOpen(false)} onPizzaCreated={refreshAdminCatalog} /> : <>
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow"><span className="live-dot" /> HORNO ENCENDIDO · BAÑOS DEL INCA</p>
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
          <label className="menu-search"><Search size={17} /><span className="sr-only">Buscar en la carta</span><input type="search" value={menuSearch} onChange={(event) => setMenuSearch(event.target.value)} placeholder="Buscar platos, ingredientes..." /></label>
          <div className="menu-toolbar"><div className="category-tabs" role="tablist" aria-label="Filtrar por categoría">{categories.map((item) => <button key={item} className={category === item ? 'active' : ''} onClick={() => setCategory(item)} role="tab" aria-selected={category === item}>{item}</button>)}</div><span className="menu-count">{searchedProducts.length.toString().padStart(2, '0')} PRODUCTOS</span></div>
          {catalogError ? <div className="empty-state"><strong>No logramos conectar con cocina.</strong><span>{catalogError} Inicia el backend y vuelve a cargar.</span></div> : !catalog ? <div className="loading-state">Encendiendo el horno...</div> : (
            <div className="menu-category-groups">
              {productGroups.map((group, groupIndex) => <section className="menu-category-section" key={group.name} aria-labelledby={`menu-category-${groupIndex}`}>
                <header className="menu-category-heading">
                  <div><p className="eyebrow">CATEGORÍA {String(groupIndex + 1).padStart(2, '0')}</p><h3 id={`menu-category-${groupIndex}`}>{group.name}</h3></div>
                  <span>{group.items.length} {group.items.length === 1 ? 'producto' : 'productos'}</span>
                </header>
                <div className="menu-product-list">
                  {group.items.map((item) => <article className={`menu-product ${item.activo ? '' : 'menu-product-disabled'}`} key={item.id}>
                    <ProductVisual image={item.imagen} categoria={item.categoria} alt={item.nombre} medida={item.subcategoria} />
                    <div className="menu-product-copy">
                      {item.subcategoria && <p className="menu-product-subcategory">{item.subcategoria}</p>}
                      <h4>{item.nombre}</h4>
                      {item.descripcion && <p className="menu-product-description">{item.descripcion}</p>}
                      {item.ingredientes.length > 0 && <p className="menu-product-ingredients">{item.ingredientes.join(' · ')}</p>}
                      {!item.activo && <span className="menu-product-unavailable">No disponible</span>}
                    </div>
                    <div className="menu-product-buy">
                      {item.precios && <select aria-label={`Tamaño de ${item.nombre}`} value={menuPizzaSizes[item.id] || 'personal'} onChange={(event) => setMenuPizzaSizes((current) => ({ ...current, [item.id]: event.target.value }))}><option value="personal">Personal · {money(item.precios.personal)}</option><option value="mediana">Mediana · {money(item.precios.mediana)}</option><option value="familiar">Familiar · {money(item.precios.familiar)}</option></select>}
                      {!item.precios && <strong>{money(item.precio)}</strong>}
                      <button disabled={!item.activo} onClick={() => addMenuItem(item)} aria-label={`Agregar ${item.nombre} al pedido`} title="Agregar al pedido"><Plus size={16} /><span>Agregar</span></button>
                      {user?.rol === 'admin' && (
                        <div className="menu-product-admin-actions">
                          <button className="admin-mini-button" type="button" onClick={() => setEditingProduct(item)}>Editar</button>
                          <button className="admin-mini-button" type="button" onClick={() => toggleMenuItemVisibility(item)}>{item.activo ? 'Ocultar' : 'Mostrar'}</button>
                          <button className="admin-mini-button danger" type="button" onClick={() => deleteMenuItem(item)}>Eliminar</button>
                        </div>
                      )}
                    </div>
                  </article>)}
                </div>
              </section>)}
              {searchedProducts.length === 0 && <p className="menu-no-results">No encontramos productos con “{menuSearch}”.</p>}
            </div>
          )}
        </section>

        <section className="customizer-section" id="personalizar">
          <div className="customizer-copy"><p className="eyebrow">HECHA A TU MANERA</p><h2>Pizza personalizada<span>.</span></h2><p>Escoge una receta como punto de partida o arma la tuya desde cero. Cambia ingredientes, revisa el precio y nosotros validamos las combinaciones.</p></div>
          <div className="customizer-controls"><label htmlFor="custom-base">Elige tu base</label><select id="custom-base" value={customBaseId} onChange={(event) => setCustomBaseId(event.target.value)}><option value="">Crear desde cero</option>{availablePizzas.map((pizza) => <option value={pizza.id} key={pizza.id}>{pizza.nombre}</option>)}</select><button className="customizer-cta" onClick={() => openBuilder(availablePizzas.find((pizza) => pizza.id === customBaseId) || null)}><ChefHat size={18} /> Personalizar pizza <ArrowRight size={17} /></button></div>
        </section>

        <section className="kitchen-band" id="nosotros"><div className="kitchen-number">02 <span>/ LA COCINA</span></div><div><p className="eyebrow">EL TIEMPO TAMBIÉN ES INGREDIENTE</p><h2>Fermentamos lento.<br /><em>Servimos caliente.</em></h2></div><p>Harina, agua, sal y paciencia. Nuestra masa descansa 48 horas antes de encontrarse con el fuego.</p><a href="#carta" aria-label="Volver al menú"><ArrowRight size={19} /></a></section>
        </>}
      </main>

      <footer className="site-footer">
        <div className="footer-brand-column">
          <a className="brand footer-brand" href="#inicio" aria-label="Pizza Pronto Italiana, inicio"><img className="brand-logo" src={brandLogo} alt="" /><span className="brand-name">Pizza Pronto <span className="brand-italiana">Italiana</span></span></a>
          <p>Buenas pizzas, buenas conversaciones.</p>
        </div>
        <div className="footer-contact">
          <h2>Visítanos</h2>
          <a href="https://maps.google.com/?q=Av.+Manco+Capac+618,+Ba%C3%B1os+del+Inca,+Cajamarca" target="_blank" rel="noreferrer"><MapPin size={17} aria-hidden="true" /><span>Baños del Inca - Cajamarca<br />Av. Manco Capac #618</span></a>
          <a href="https://wa.me/51934216618" target="_blank" rel="noopener noreferrer"><Phone size={17} aria-hidden="true" /><span>934 216 618 (WhatsApp)</span></a>
        </div>
        <div className="footer-social">
          <h2>Síguenos</h2>
          <a href="https://www.facebook.com/pizzaprontoitaliana" target="_blank" rel="noopener noreferrer"><Facebook size={17} aria-hidden="true" /><span>PIZZA Pronto</span></a>
          <a href="https://www.instagram.com/pizzapronto.italiana/" target="_blank" rel="noreferrer"><Instagram size={17} aria-hidden="true" /><span>pizzapronto.italiana</span></a>
          <a href="https://www.tiktok.com/@pizzaprontoitaliana" target="_blank" rel="noreferrer"><Video size={17} aria-hidden="true" /><span>@pizzaprontoitaliana</span></a>
        </div>
        <div className="footer-bottom"><span>Pizza Pronto Italiana · Baños del Inca, Cajamarca</span><span>© {new Date().getFullYear()} Todos los derechos reservados</span></div>
      </footer>

      {notice && <div className="toast" role="status">{notice}</div>}

      {editingProduct && <PizzaCreateForm mode={editingProduct.es_pizza ? 'edit' : 'menu-edit'} initialPizza={editingProduct} onClose={() => setEditingProduct(null)} onCreated={async (updatedProduct) => {
        await refreshAdminCatalog()
        setEditingProduct(null)
        showNotice(updatedProduct?.nombre ? `${updatedProduct.nombre} actualizado` : 'Producto actualizado')
      }} />}

      {builder && <div className="overlay" onMouseDown={(event) => event.target === event.currentTarget && setBuilder(null)}><section className="builder-panel" role="dialog" aria-modal="true" aria-labelledby="builder-title"><div className="panel-top"><span className="eyebrow">TU PIZZA, TUS REGLAS</span><button className="icon-button" onClick={() => setBuilder(null)} aria-label="Cerrar"><X size={20} /></button></div><h2 id="builder-title">{builder.nombre}</h2><p className="builder-description">{builder.descripcion}</p><label className="field-label" htmlFor="size">Tamaño</label><div className="size-options" id="size">{catalog?.tamanos.map((item) => <button key={item.id} className={size === item.id ? 'selected' : ''} onClick={() => setSize(item.id)}><span>{item.nombre.split(' ')[0]}</span><small>{item.nombre.match(/\d+ cm/)?.[0]} · {item.desc.split('·')[1]}</small></button>)}</div>
          <div className="ingredient-head"><label className="field-label">Ingredientes</label><span>Elige masa y salsa</span></div><div className="ingredient-list">{ingredientGroups.map((group) => <fieldset className="ingredient-group" key={group.id}><legend>{group.nombre}<small>{group.ayuda}</small></legend><div className="ingredient-options">{catalog.ingredientes.filter((item) => item.grupo === group.id).map((item) => { const selected = ingredients.includes(item.id); const blocked = quote?.bloqueados?.[item.id]; return <button key={item.id} className={`ingredient-option ${selected ? 'chosen' : ''}`} disabled={Boolean(blocked)} title={blocked || item.nombre} onClick={() => setIngredients((current) => selected ? current.filter((id) => id !== item.id) : [...current, item.id])}><span className="ingredient-emoji">{item.emoji}</span><span>{item.nombre}</span><small>{Number(item.precio) === 0 ? 'Incluido' : `+${money(item.precio)}`}</small>{selected && <Check className="ingredient-check" size={15} />}</button>})}</div></fieldset>)}</div>
          {quote?.errores?.length > 0 && <p className="form-error">{quote.errores[0].detalle}</p>}{quoteError && <p className="form-error">{quoteError}</p>}
          <div className="builder-bottom"><div><small>PRECIO</small><strong>{quote ? money(quote.total) : '...'}</strong></div><button className="primary-button" disabled={!quote?.ok} onClick={addConfiguredPizza}>Añadir al pedido <ArrowRight size={17} /></button></div>
        </section></div>}

      {cartOpen && <div className="overlay" onMouseDown={(event) => event.target === event.currentTarget && setCartOpen(false)}><aside className="cart-panel" role="dialog" aria-modal="true" aria-labelledby="cart-title"><div className="panel-top"><span className="eyebrow">{checkout ? 'CASI EN TU MESA' : 'TU SELECCIÓN'}</span><button className="icon-button" onClick={() => setCartOpen(false)} aria-label="Cerrar pedido"><X size={20} /></button></div><h2 id="cart-title">{checkout ? 'Datos de entrega' : 'El pedido.'}</h2>
          {!checkout ? (
            cart.length === 0 ? (
              <div className="cart-empty">
                <span>🍕</span>
                <strong>Tu pedido está vacío.</strong>
                <p>Encuentra algo rico en la carta.</p>
                <button className="text-button" onClick={() => setCartOpen(false)}>
                  Volver a la carta <ArrowRight size={16} />
                </button>
              </div>
            ) : (
              <>
                <div className="cart-items">
                  {cart.map((item) => (
                    <article className="cart-item" key={item.key}>
                      <div className="cart-item-icon">{item.menu_item_id && !item.es_pizza ? '🍽️' : '🍕'}</div>
                      <div className="cart-item-copy">
                        <strong>{item.nombre}</strong>
                        {(item.tamano_id || item.subcategoria) && <span>{item.tamano_id ? catalog?.tamanos.find((t) => t.id === item.tamano_id)?.nombre : item.subcategoria}</span>}
                        {item.descripcion && <span>{item.descripcion}</span>}
                        {item.detalle?.length > 0 && <span>{item.detalle.map((detail) => detail.nombre).join(', ')}</span>}
                        <span>{item.cantidad} × {money(item.precio_unitario)}</span>
                        <b>{money(item.precio_unitario * item.cantidad)}</b>
                      </div>
                      <div className="quantity-control">
                        <button onClick={() => changeQuantity(item.key, -1)} aria-label="Quitar una"><Minus size={13} /></button>
                        <span>{item.cantidad}</span>
                        <button onClick={() => changeQuantity(item.key, 1)} aria-label="Añadir una"><Plus size={13} /></button>
                      </div>
                    </article>
                  ))}
                </div>
                <div className="cart-totals">
                  <div><span>Subtotal</span><b>{money(subtotal)}</b></div>
                  <div><span>{customer.tipo_entrega === 'delivery' ? 'Delivery' : customer.tipo_entrega === 'retiro_local' ? 'Retiro en local' : 'Consumo en local'}</span><b>{delivery ? money(delivery) : 'Sin costo'}</b></div>
                  <div className="total-line"><span>Total</span><b>{money(subtotal + delivery)}</b></div>
                </div>
                <button className="primary-button checkout-button" disabled={!cart.length} onClick={() => setCheckout(true)}>
                  Continuar con el pedido <ArrowRight size={17} />
                </button>
              </>
            )
          ) : (
            <form className="checkout-form" onSubmit={placeOrder}>
              <section className="checkout-order-list" aria-label="Resumen del pedido">
                <div className="checkout-order-heading"><strong>Tu pedido</strong><span>{units} {units === 1 ? 'producto' : 'productos'}</span></div>
                {cart.map((item) => <div className="checkout-order-line" key={item.key}><span><strong>{item.nombre}</strong><small>{item.tamano_id ? catalog?.tamanos.find((t) => t.id === item.tamano_id)?.nombre : item.subcategoria || item.descripcion || 'Carta'} · {item.cantidad} × {money(item.precio_unitario)}</small></span><b>{money(item.precio_unitario * item.cantidad)}</b></div>)}
              </section>
              <label>Nombre completo<input required autoComplete="name" value={customer.nombre} onChange={(event) => setCustomer({ ...customer, nombre: event.target.value })} /></label>
              <label>Teléfono<input required autoComplete="tel" inputMode="tel" value={customer.telefono} onChange={(event) => setCustomer({ ...customer, telefono: event.target.value })} /></label>
              <label>¿Cómo recibes tu pedido?<span className="select-wrap"><select value={customer.tipo_entrega} onChange={(event) => setCustomer({ ...customer, tipo_entrega: event.target.value })}><option value="delivery">Delivery</option><option value="retiro_local">Retiro en local</option><option value="comer_local">Comer en local</option></select><ChevronDown size={16} /></span></label>
              {customer.tipo_entrega === 'delivery' && <>
                <label>Dirección<input required autoComplete="street-address" value={customer.direccion} onChange={(event) => setCustomer({ ...customer, direccion: event.target.value })} /></label>
                <label>Referencia<input required value={customer.referencia} onChange={(event) => setCustomer({ ...customer, referencia: event.target.value })} /></label>
                <label>DNI o RUC <span className="optional-label">Opcional</span><input inputMode="numeric" value={customer.dni_ruc} onChange={(event) => setCustomer({ ...customer, dni_ruc: event.target.value })} /></label>
              </>}
              {customer.tipo_entrega === 'retiro_local' && <div className="checkout-location"><span>RETIRO EN LOCAL</span><strong>Av. Manco Cápac 618, Cajamarca 06004</strong></div>}
              {customer.tipo_entrega === 'comer_local' && <>
                <div className="checkout-location"><span>TE ESPERAMOS EN</span><strong>Av. Manco Cápac 618, Cajamarca 06004</strong></div>
                <label>Número de mesa<input required inputMode="numeric" value={customer.numero_mesa} onChange={(event) => setCustomer({ ...customer, numero_mesa: event.target.value })} /></label>
                <label>DNI o RUC para la boleta<input required inputMode="numeric" value={customer.dni_ruc} onChange={(event) => setCustomer({ ...customer, dni_ruc: event.target.value })} /></label>
              </>}
              <fieldset className="payment-methods"><legend>Método de pago</legend><div className="payment-options" role="group" aria-label="Método de pago">
                <button type="button" className={payment === 'efectivo' ? 'selected' : ''} aria-pressed={payment === 'efectivo'} onClick={() => { setPayment('efectivo'); setCashTendered('') }}><Banknote size={17} /> Efectivo</button>
                <button type="button" className={payment === 'yape' ? 'selected' : ''} aria-pressed={payment === 'yape'} onClick={() => { setPayment('yape'); setCashTendered('') }}><Smartphone size={17} /> Yape</button>
                <button type="button" className={payment === 'tarjeta' ? 'selected' : ''} aria-pressed={payment === 'tarjeta'} onClick={() => { setPayment('tarjeta'); setCashTendered('') }}><CreditCard size={17} /> Tarjeta</button>
              </div></fieldset>
              {payment === 'efectivo' && <>
                <label>¿Con cuánto pagarás?<input required type="number" min={orderTotal} step="0.1" inputMode="decimal" value={cashTendered} onChange={(event) => setCashTendered(event.target.value)} placeholder={orderTotal.toFixed(2)} /></label>
                {cashTendered !== '' && <p className={cashChange >= 0 ? 'change-summary' : 'form-error'}>{cashChange >= 0 ? `Tu vuelto: ${money(cashChange)}` : `Faltan ${money(Math.abs(cashChange))} para completar el pago.`}</p>}
              </>}
              <div className="checkout-total"><span>Total del pedido</span><strong>{money(subtotal + delivery)}</strong></div>
              {notice && <p className="form-error">{notice}</p>}
              <button className="primary-button checkout-button" disabled={busy || (payment === 'efectivo' && (cashTendered === '' || cashChange < 0))}>{busy ? 'Registrando...' : 'Confirmar pedido'} <ArrowRight size={17} /></button>
              <button type="button" className="back-button" onClick={() => { setCheckout(false); setNotice('') }}>Volver al carrito</button>
            </form>
          )}
        </aside></div>}

      {order && (
        <div className="overlay confirmation-overlay">
          <section className="confirmation-dialog" role="dialog" aria-modal="true" aria-labelledby="confirmation-title">
            <span className="confirmation-check"><Check size={24} /></span>
            <p className="eyebrow">{order.items.some((item) => item.es_pizza) ? 'EN COCINA' : 'PEDIDO RECIBIDO'}</p>
            <h2 id="confirmation-title">¡Gracias, {order.cliente}!</h2>
            <p>Recibimos tu pedido y el equipo ya está trabajando en él.</p>
            <div className="order-code"><span>CÓDIGO DE PEDIDO</span><strong>{order.codigo}</strong></div>
            {order.estimado_minutos != null && <p className="customer-order-eta">Tiempo estimado de salida: aproximadamente {order.estimado_minutos} min.</p>}
            <div className="confirmation-details">
              <div><span>Teléfono</span><b>{order.telefono}</b></div>
              <div><span>Entrega</span><b>{order.tipo_entrega === 'delivery' ? 'Delivery' : order.tipo_entrega === 'retiro_local' ? 'Retiro en local' : 'Comer en local'}</b></div>
              {order.direccion && <div><span>Dirección</span><b>{order.direccion}</b></div>}
              {order.referencia && <div><span>Referencia</span><b>{order.referencia}</b></div>}
              {order.numero_mesa && <div><span>Mesa</span><b>{order.numero_mesa}</b></div>}
              {order.dni_ruc && <div><span>DNI / RUC</span><b>{order.dni_ruc}</b></div>}
            </div>
            <div className="confirmation-items">{order.items.map((item, index) => <div key={`${item.nombre}-${index}`}><span><strong>{item.nombre}</strong><small>{item.tamano ? `${item.tamano} · ` : ''}{item.cantidad} × {money(item.precio_unitario)}</small></span><b>{money(item.total)}</b></div>)}</div>
            <div className="confirmation-payment"><span>Pago · {order.metodo_pago === 'efectivo' ? 'Efectivo' : order.metodo_pago === 'yape' ? 'Yape' : 'Tarjeta'}</span>{order.metodo_pago === 'efectivo' && <span>Pagó {money(order.paga_con)} · Vuelto {money(order.vuelto)}</span>}</div>
            <div className="order-total"><span>Total del pedido</span><strong>{money(order.total)}</strong></div>
            <button className="primary-button" onClick={() => { setOrder(null); setCartOpen(false) }}>Volver a la carta <ArrowRight size={17} /></button>
          </section>
        </div>
      )}
    </>
  )
}
