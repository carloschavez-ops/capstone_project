import { useEffect, useState } from 'react'
import { apiJson } from './api.js'
import './operations.css'
import RecipeEditor from './RecipeEditor.jsx'
import OrderReport from './OrderReport.jsx'

function useResource(url) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)
  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    apiJson(url).then((result) => { if (active) setData(result) })
      .catch((failure) => { if (active) setError(failure.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [url, version])
  return { data, error, loading, reload: () => setVersion((value) => value + 1) }
}

function useAction(reload) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  async function run(action, message = 'Cambios guardados.') {
    setBusy(true); setError(''); setNotice('')
    try {
      const result = await action()
      reload?.()
      setNotice(message)
      return result
    } catch (failure) {
      setError(failure.message)
      return null
    } finally { setBusy(false) }
  }
  return { busy, error, notice, run }
}

function Feedback({ resource, action }) {
  return <>
    {(resource?.error || action?.error) && <p role="alert" className="ops-error">{action?.error || resource?.error}</p>}
    {action?.notice && <p role="status" className="ops-notice">{action.notice}</p>}
    {resource?.loading && <p role="status">Cargando información…</p>}
  </>
}

const formatDate = (value) => value ? new Intl.DateTimeFormat('es-PE', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Lima' }).format(new Date(value)) : '—'

function Staff() {
  const resource = useResource('/api/admin/staff')
  const action = useAction(resource.reload)
  const [form, setForm] = useState({ nombre: '', email: '', password: '', rol: 'cocina' })
  const [edits, setEdits] = useState({})
  async function create(event) {
    event.preventDefault()
    if (await action.run(() => apiJson('/api/admin/staff', { method: 'POST', body: form }), 'Cuenta individual creada.')) setForm({ nombre: '', email: '', password: '', rol: 'cocina' })
  }
  function edit(id, changes) { setEdits((current) => ({ ...current, [id]: { ...current[id], ...changes } })) }
  return <>
    <h2>Cuentas del personal</h2>
    <p>Cada trabajador utiliza su propia cuenta. Cambiar rol, contraseña o acceso cierra sus sesiones anteriores.</p>
    <Feedback resource={resource} action={action} />
    <form className="ops-form" onSubmit={create}>
      <label>Nombre<input required maxLength={120} value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} autoComplete="off" /></label>
      <label>Correo<input type="email" required maxLength={254} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} autoComplete="off" /></label>
      <label>Contraseña inicial<input type="password" required minLength={12} maxLength={256} autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /><small>Mínimo 12 caracteres.</small></label>
      <label>Función<select value={form.rol} onChange={(e) => setForm({ ...form, rol: e.target.value })}><option value="cocina">Cocina</option><option value="caja">Caja</option></select></label>
      <button disabled={action.busy}>Crear cuenta</button>
    </form>
    <div className="ops-table-wrap"><table><caption>Cuentas operativas</caption><thead><tr><th>Cuenta</th><th>Función</th><th>Acceso</th><th>Nueva contraseña</th><th>Acción</th></tr></thead><tbody>
      {resource.data?.usuarios.map((user) => {
        const values = { ...user, ...edits[user.id] }
        return <tr key={user.id}><td><strong>{user.nombre}</strong><br />{user.email}</td><td>{user.rol === 'admin' ? 'Administración' : <select aria-label={`Función de ${user.nombre}`} value={values.rol} onChange={(e) => edit(user.id, { rol: e.target.value })}><option value="cocina">Cocina</option><option value="caja">Caja</option></select>}</td><td>{user.rol === 'admin' ? 'Activo' : <label className="ops-check"><input type="checkbox" checked={values.activo} onChange={(e) => edit(user.id, { activo: e.target.checked })} />Activo</label>}</td><td>{user.rol !== 'admin' && <input aria-label={`Nueva contraseña de ${user.nombre}`} type="password" minLength={12} autoComplete="new-password" placeholder="Mantener actual" value={edits[user.id]?.password || ''} onChange={(e) => edit(user.id, { password: e.target.value })} />}</td><td>{user.rol !== 'admin' && <button disabled={action.busy || !edits[user.id]} onClick={async () => {
          const body = { rol: values.rol, activo: values.activo }
          if (edits[user.id]?.password) body.password = edits[user.id].password
          if (await action.run(() => apiJson(`/api/admin/staff/${user.id}`, { method: 'PATCH', body }))) setEdits((current) => { const next = { ...current }; delete next[user.id]; return next })
        }}>Guardar</button>}</td></tr>
      })}
    </tbody></table></div>
    <h3>Permisos por función</h3>
    <div className="ops-table-wrap"><table><thead><tr><th>Función</th><th>Operaciones permitidas</th></tr></thead><tbody>{Object.entries(resource.data?.roles || {}).filter(([role]) => role !== 'cliente').map(([role, permissions]) => <tr key={role}><th scope="row">{role}</th><td>{permissions.join(', ')}</td></tr>)}</tbody></table></div>
  </>
}

function Audit() {
  const [filters, setFilters] = useState({ entidad: '', entidad_id: '', usuario_id: '', desde: '', hasta: '' })
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const resource = useResource(`/api/admin/audit?${query}&page=${page}`)
  return <>
    <h2>Historial de cambios</h2><p>Consulta quién cambió el catálogo, inventario o estados. Las cantidades anteriores y posteriores explican cada variación. Los registros se conservan sin opción de edición.</p>
    <Feedback resource={resource} />
    <form className="ops-form" onSubmit={(e) => { e.preventDefault(); setPage(1); setQuery(new URLSearchParams(Object.entries(filters).filter(([, value]) => value)).toString()) }}>
      <label>Entidad<select value={filters.entidad} onChange={(e) => setFilters({ ...filters, entidad: e.target.value })}><option value="">Todas</option>{['inventario', 'pedidos', 'pizzas', 'menu_items', 'usuarios', 'mermas', 'respaldo', 'pilotos', 'resultados_piloto', 'mediciones_piloto'].map((name) => <option key={name}>{name}</option>)}</select></label>
      <label>Identificador<input value={filters.entidad_id} onChange={(e) => setFilters({ ...filters, entidad_id: e.target.value })} /></label>
      <label>ID de usuario<input type="number" min="1" value={filters.usuario_id} onChange={(e) => setFilters({ ...filters, usuario_id: e.target.value })} /></label>
      <label>Desde<input type="date" value={filters.desde} onChange={(e) => setFilters({ ...filters, desde: e.target.value })} /></label>
      <label>Hasta<input type="date" value={filters.hasta} onChange={(e) => setFilters({ ...filters, hasta: e.target.value })} /></label>
      <button>Filtrar</button>
    </form>
    <p>{resource.data?.total || 0} registros · Hora de Perú</p>
    <div className="ops-table-wrap"><table><thead><tr><th>Fecha y actor</th><th>Operación</th><th>Entidad</th><th>Cambios</th></tr></thead><tbody>{resource.data?.registros.map((row) => <tr key={row.id}><td>{formatDate(row.fecha)}<br />{row.actor}<br /><small>{row.rol}</small></td><td>{row.operacion}</td><td>{row.entidad}<br /><code>{row.entidad_id}</code></td><td><details><summary>Ver detalle</summary><pre>{JSON.stringify(row.cambios, null, 2)}</pre></details></td></tr>)}</tbody></table></div>
    {resource.data?.total === 0 && <p>No hay cambios para estos filtros.</p>}
    <Pagination page={page} total={resource.data?.total || 0} onChange={setPage} />
  </>
}

function Pagination({ page, total, onChange }) {
  return <div className="ops-actions"><button disabled={page <= 1} onClick={() => onChange(page - 1)}>Anterior</button><span>Página {page} de {Math.max(1, Math.ceil(total / 50))}</span><button disabled={page * 50 >= total} onClick={() => onChange(page + 1)}>Siguiente</button></div>
}

function Backups() {
  const resource = useResource('/api/admin/backups')
  const action = useAction(resource.reload)
  return <>
    <h2>Respaldo y recuperación</h2><p>Las copias incluyen SQLite e imágenes subidas. Guarda una copia descargada en otro equipo o almacenamiento privado.</p>
    <Feedback resource={resource} action={action} />
    {resource.data?.alerta && <p className="ops-warning" role="status">{resource.data.alerta}</p>}
    <div className="ops-actions"><button disabled={action.busy} onClick={() => action.run(() => apiJson('/api/admin/backups', { method: 'POST' }), 'Copia creada. Verifica su recuperación y descárgala.')}>{action.busy ? 'Procesando…' : 'Crear copia ahora'}</button><button disabled={action.busy} onClick={resource.reload}>Actualizar</button></div>
    <p>Metas: antigüedad máxima de la copia de 24 horas y recuperación en 2 horas. La prueba mide una restauración local aislada; el tiempo de un incidente depende también de la operación del servidor.</p>
    <div className="ops-table-wrap"><table><thead><tr><th>Copia</th><th>Antigüedad</th><th>Recuperación de prueba</th><th>Acciones</th></tr></thead><tbody>{resource.data?.copias.map((copy) => <tr key={copy.archivo}><td><strong>{formatDate(copy.creado_en)}</strong><br /><small>{copy.archivo}</small><br />{copy.bytes ? `${(copy.bytes / 1024 / 1024).toFixed(2)} MB` : copy.error}</td><td>{copy.antiguedad_horas ?? '—'} h<br />{copy.cumple_rpo ? 'Dentro de la meta' : 'Fuera de la meta'}</td><td>{copy.verificacion ? <>{formatDate(copy.verificacion.verificado_en)}<br />{copy.verificacion.rto_segundos} segundos<br />{copy.verificacion.conteos.pedidos} pedidos y {copy.verificacion.imagenes} imágenes recuperados<br />RPO al verificar: {copy.verificacion.rpo_horas} h</> : 'Sin verificar'}</td><td><div className="ops-actions"><a className="ops-link" href={`/api/admin/backups/${encodeURIComponent(copy.archivo)}/download`}>Descargar ZIP</a><button disabled={action.busy || !!copy.error} onClick={() => action.run(() => apiJson(`/api/admin/backups/${encodeURIComponent(copy.archivo)}/verify`, { method: 'POST' }), 'Restauración de prueba terminada. Consulta las mediciones en la tabla.')}>Verificar recuperación</button></div></td></tr>)}</tbody></table></div>
    {!resource.loading && !resource.data?.copias.length && <p>Todavía no hay copias.</p>}
    <h3>Restauración del servicio</h3><p>El responsable técnico debe detener el servidor y usar el procedimiento de recuperación del manual de operación. La herramienta verifica la copia, conserva los originales e invalida las sesiones anteriores. La pantalla de verificación no reemplaza los datos en uso.</p>
  </>
}

function Pilot() {
  const list = useResource('/api/admin/pilot')
  const [selected, setSelected] = useState('')
  const [name, setName] = useState('')
  const [owner, setOwner] = useState('')
  const [cases, setCases] = useState(null)
  const action = useAction(list.reload)
  const activeCases = cases || list.data?.casos_propuestos || []
  return <>
    <h2>Aceptación del piloto</h2><p>Define las tareas antes de la ejecución. Registra resultados reales del personal, evidencia y correcciones. Una cuenta administradora registra la decisión acordada con el representante del negocio.</p>
    <Feedback resource={list} action={action} />
    <details><summary>Crear una ejecución del piloto</summary><form className="ops-form ops-block" onSubmit={async (e) => {
      e.preventDefault()
      const result = await action.run(() => apiJson('/api/admin/pilot', { method: 'POST', body: { nombre: name, responsable: owner, casos: activeCases } }), 'Protocolo creado; ya puedes registrar su ejecución.')
      if (result) { setSelected(String(result.piloto.id)); setName(''); setOwner('') }
    }}>
      <div className="ops-grid"><label>Nombre del piloto<input required maxLength={160} value={name} onChange={(e) => setName(e.target.value)} /></label><label>Responsable de ejecución<input required maxLength={120} value={owner} onChange={(e) => setOwner(e.target.value)} /></label></div>
      <h3>Tareas y criterios previos</h3>
      {activeCases.map((task, index) => <fieldset key={task.id}><legend>{task.id}</legend><label>Tarea<input required maxLength={160} value={task.nombre} onChange={(e) => setCases(activeCases.map((item, i) => i === index ? { ...item, nombre: e.target.value } : item))} /></label><label>Criterio de aceptación<textarea required maxLength={1000} value={task.criterio} onChange={(e) => setCases(activeCases.map((item, i) => i === index ? { ...item, criterio: e.target.value } : item))} /></label></fieldset>)}
      <button disabled={action.busy || !activeCases.length}>Guardar protocolo y abrir piloto</button>
    </form></details>
    <label className="ops-selector">Ejecución<select value={selected} onChange={(e) => setSelected(e.target.value)}><option value="">Selecciona un piloto</option>{list.data?.pilotos.map((pilot) => <option key={pilot.id} value={pilot.id}>{pilot.nombre} · {pilot.estado}</option>)}</select></label>
    {selected && <PilotRun key={selected} id={selected} onChanged={list.reload} />}
    {!list.loading && !list.data?.pilotos.length && <p>No se han registrado ejecuciones del piloto.</p>}
  </>
}

function PilotRun({ id, onChanged }) {
  const resource = useResource(`/api/admin/pilot/${id}`)
  const action = useAction(() => { resource.reload(); onChanged() })
  const pilot = resource.data?.piloto
  const [result, setResult] = useState({ caso_id: '', participante: '', resultado: 'aprobado', evidencia: '', defecto: '', responsable_correccion: '', sin_ayuda: false })
  const [decision, setDecision] = useState({ decision: 'condicionado', representante_negocio: '', conclusion: '', impedimentos: '' })
  const [corrections, setCorrections] = useState({})
  if (!pilot) return <Feedback resource={resource} action={action} />
  return <>
    <h3>{pilot.nombre}</h3><p>Responsable: {pilot.responsable} · {pilot.estado} · Creado {formatDate(pilot.creado_en)}</p><Feedback resource={resource} action={action} />
    <details><summary>Consultar protocolo</summary><ol>{pilot.casos.map((task) => <li key={task.id}><strong>{task.id} {task.nombre}</strong><p>{task.criterio}</p></li>)}</ol></details>
    <p>Tareas sin ejecutar: {pilot.tareas_sin_ejecutar.join(', ') || 'ninguna'} · Defectos abiertos: {pilot.defectos_abiertos}</p>
    {pilot.usabilidad && <p role="status">Pedido sin ayuda: {pilot.usabilidad.completaron_sin_ayuda} de {pilot.usabilidad.participantes} participantes ({pilot.usabilidad.porcentaje ?? 'Sin datos'}{pilot.usabilidad.porcentaje == null ? '' : '%'}). Meta: {pilot.usabilidad.meta_porcentaje}%. {pilot.usabilidad.cumple_meta == null ? 'Faltan ejecuciones de P06.' : pilot.usabilidad.cumple_meta ? 'Meta alcanzada en esta ejecución.' : 'Meta no alcanzada.'}</p>}
    {pilot.estado === 'abierto' && <form className="ops-form" onSubmit={async (e) => {
      e.preventDefault()
      if (await action.run(() => apiJson(`/api/admin/pilot/${id}/results`, { method: 'POST', body: result }), 'Resultado registrado.')) setResult({ ...result, participante: '', evidencia: '', defecto: '', responsable_correccion: '' })
    }}>
      <label>Tarea<select required value={result.caso_id} onChange={(e) => setResult({ ...result, caso_id: e.target.value })}><option value="">Selecciona</option>{pilot.casos.map((task) => <option key={task.id} value={task.id}>{task.id} {task.nombre}</option>)}</select></label>
      <label>Código del participante<input required pattern="[A-Za-z0-9_-]{2,40}" maxLength={40} placeholder="P001" value={result.participante} onChange={(e) => setResult({ ...result, participante: e.target.value })} /><small>Usa códigos anónimos.</small></label>
      <label>Resultado<select value={result.resultado} onChange={(e) => setResult({ ...result, resultado: e.target.value })}><option value="aprobado">Aprobado</option><option value="fallido">Fallido</option></select></label>
      <label>Evidencia o ubicación<textarea required maxLength={1000} value={result.evidencia} onChange={(e) => setResult({ ...result, evidencia: e.target.value })} /></label>
      <label>Defecto<textarea required={result.resultado === 'fallido'} maxLength={1000} value={result.defecto} onChange={(e) => setResult({ ...result, defecto: e.target.value })} /></label>
      <label>Responsable de corrección<input required={result.resultado === 'fallido'} maxLength={120} value={result.responsable_correccion} onChange={(e) => setResult({ ...result, responsable_correccion: e.target.value })} /></label>
      <label className="ops-check"><input type="checkbox" checked={result.sin_ayuda} onChange={(e) => setResult({ ...result, sin_ayuda: e.target.checked })} />Completó la tarea sin ayuda</label><button disabled={action.busy}>Registrar resultado</button>
    </form>}
    <div className="ops-table-wrap"><table><thead><tr><th>Tarea y participante</th><th>Resultado y evidencia</th><th>Defecto y corrección</th></tr></thead><tbody>{pilot.resultados.map((row) => <tr key={row.id}><td>{row.caso_id} · {row.participante}<br />{formatDate(row.fecha)}<br />{row.sin_ayuda ? 'Sin ayuda' : 'Con ayuda o sin completar'}</td><td>{row.resultado}<p>{row.evidencia}</p></td><td>{row.defecto || 'Sin defecto'}{row.defecto && <p>Responsable: {row.responsable_correccion}</p>}{row.resuelto && <p>Resuelto: {row.evidencia_correccion}</p>}{pilot.estado === 'abierto' && row.resultado === 'fallido' && !row.resuelto && <form onSubmit={(e) => { e.preventDefault(); action.run(() => apiJson(`/api/admin/pilot/results/${row.id}`, { method: 'PATCH', body: { evidencia_correccion: corrections[row.id] || '' } }), 'Corrección registrada.') }}><label>Evidencia de corrección<textarea required maxLength={1000} value={corrections[row.id] || ''} onChange={(e) => setCorrections({ ...corrections, [row.id]: e.target.value })} /></label><button disabled={action.busy}>Resolver defecto</button></form>}</td></tr>)}</tbody></table></div>
    {pilot.estado === 'abierto' ? <><h3>Emitir acta de aceptación</h3><p>El acta cierra la ejecución y conserva una copia de todos sus resultados. Para repetir pruebas después del cierre, crea una nueva ejecución.</p><form className="ops-form" onSubmit={(e) => { e.preventDefault(); action.run(() => apiJson(`/api/admin/pilot/${id}/decision`, { method: 'POST', body: decision }), 'Acta guardada y ejecución cerrada.') }}>
      <label>Decisión<select value={decision.decision} onChange={(e) => setDecision({ ...decision, decision: e.target.value })}><option value="condicionado">Condicionado</option><option value="rechazado">Rechazado</option><option value="aceptado">Aceptado</option></select></label>
      <label>Representante del negocio<input required maxLength={120} value={decision.representante_negocio} onChange={(e) => setDecision({ ...decision, representante_negocio: e.target.value })} /></label>
      <label>Conclusión acordada<textarea required maxLength={2000} value={decision.conclusion} onChange={(e) => setDecision({ ...decision, conclusion: e.target.value })} /></label>
      <label>Impedimentos para la puesta en servicio<textarea required={decision.decision !== 'aceptado'} maxLength={2000} value={decision.impedimentos} onChange={(e) => setDecision({ ...decision, impedimentos: e.target.value })} /></label>
      <button disabled={action.busy}>Guardar acta y cerrar</button>
    </form></> : <><h3>Acta conservada</h3><p><strong>{pilot.acta.decision}</strong> · {formatDate(pilot.acta.fecha)} · Representante: {pilot.acta.representante_negocio}</p><p>{pilot.acta.conclusion}</p><p>Impedimentos: {pilot.acta.impedimentos || 'Sin impedimentos registrados.'}</p></>}
  </>
}

const metricLabels = { tasa_errores: 'Pedidos con errores (%)', tiempo_medio_minutos: 'Tiempo medio (min)', completitud: 'Pedidos completos (%)', exactitud_inventario: 'Exactitud de inventario (%)' }
const initialMeasurement = { fase: 'antes', fecha: '', turno: 'tarde', modalidad: 'retiro_local', condiciones: '', pedidos: '', errores: '', completos: '', minutos_totales: '', pedidos_cronometrados: '', insumos_revisados: '', insumos_exactos: '', limitaciones: '', excluida: false, motivo_exclusion: '' }
const countLabels = { pedidos: 'Pedidos observados', errores: 'Pedidos con al menos un error', completos: 'Pedidos con todos los datos', minutos_totales: 'Suma de minutos de atención', pedidos_cronometrados: 'Pedidos cronometrados', insumos_revisados: 'Insumos contados físicamente', insumos_exactos: 'Insumos con stock exacto' }

function Indicators() {
  const [form, setForm] = useState(initialMeasurement)
  const [filters, setFilters] = useState({ desde: '', hasta: '', turno: '', modalidad: '' })
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [reasons, setReasons] = useState({})
  const resource = useResource(`/api/admin/indicators?${query}&page=${page}`)
  const action = useAction(resource.reload)
  const report = resource.data
  return <>
    <h2>Indicadores antes y después del piloto</h2><p>Registra observaciones anónimas por fecha, turno y modalidad. Usa el mismo nombre de condiciones para muestras comparables, por ejemplo, dos personas en atención y el mismo método de conteo.</p>
    <Feedback resource={resource} action={action} />
    <details><summary>Registrar una medición real</summary><form className="ops-form" onSubmit={async (e) => {
      e.preventDefault()
      const body = { ...form }
      Object.keys(countLabels).forEach((key) => { body[key] = Number(form[key]) })
      if (await action.run(() => apiJson('/api/admin/indicators', { method: 'POST', body }), 'Medición anónima guardada.')) setForm(initialMeasurement)
    }}>
      <label>Fase<select value={form.fase} onChange={(e) => setForm({ ...form, fase: e.target.value })}><option value="antes">Antes</option><option value="despues">Después</option></select></label>
      <label>Fecha<input required type="date" value={form.fecha} onChange={(e) => setForm({ ...form, fecha: e.target.value })} /></label>
      <label>Turno<select value={form.turno} onChange={(e) => setForm({ ...form, turno: e.target.value })}><option value="manana">Mañana</option><option value="tarde">Tarde</option><option value="noche">Noche</option></select></label>
      <label>Modalidad<select value={form.modalidad} onChange={(e) => setForm({ ...form, modalidad: e.target.value })}><option value="retiro_local">Retiro</option><option value="delivery">Delivery</option><option value="comer_local">Consumo en local</option></select></label>
      <label>Condiciones de observación<input required maxLength={160} value={form.condiciones} onChange={(e) => setForm({ ...form, condiciones: e.target.value })} /></label>
      {Object.entries(countLabels).map(([key, label]) => <label key={key}>{label}<input required type="number" min="0" max={key === 'minutos_totales' ? 10000000 : 1000000} step={key === 'minutos_totales' ? '0.01' : '1'} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} /></label>)}
      <label>Limitaciones de la observación<textarea maxLength={1000} value={form.limitaciones} onChange={(e) => setForm({ ...form, limitaciones: e.target.value })} /></label>
      <label className="ops-check"><input type="checkbox" checked={form.excluida} onChange={(e) => setForm({ ...form, excluida: e.target.checked })} />Excluir del análisis</label>
      <label>Motivo de exclusión<textarea required={form.excluida} maxLength={500} value={form.motivo_exclusion} onChange={(e) => setForm({ ...form, motivo_exclusion: e.target.value })} /></label><button disabled={action.busy}>Guardar medición</button>
    </form></details>
    <form className="ops-form" onSubmit={(e) => { e.preventDefault(); setPage(1); setQuery(new URLSearchParams(Object.entries(filters).filter(([, value]) => value)).toString()) }}>
      <label>Desde<input type="date" value={filters.desde} onChange={(e) => setFilters({ ...filters, desde: e.target.value })} /></label><label>Hasta<input type="date" value={filters.hasta} onChange={(e) => setFilters({ ...filters, hasta: e.target.value })} /></label>
      <label>Turno<select value={filters.turno} onChange={(e) => setFilters({ ...filters, turno: e.target.value })}><option value="">Todos</option><option value="manana">Mañana</option><option value="tarde">Tarde</option><option value="noche">Noche</option></select></label>
      <label>Modalidad<select value={filters.modalidad} onChange={(e) => setFilters({ ...filters, modalidad: e.target.value })}><option value="">Todas</option><option value="retiro_local">Retiro</option><option value="delivery">Delivery</option><option value="comer_local">Local</option></select></label><button>Aplicar filtros</button>
    </form>
    {report && <>
      <p role="status">{report.mensaje} {report.total} muestras registradas, {report.excluidas} excluidas.</p>
      <h3>Comparación en condiciones coincidentes</h3><p>{report.comparacion.criterio}</p>
      <div className="ops-table-wrap"><table><thead><tr><th>Indicador</th><th>Antes</th><th>Después</th><th>Diferencia</th></tr></thead><tbody>{Object.entries(metricLabels).map(([key, label]) => <tr key={key}><th scope="row">{label}</th>{['antes', 'despues'].map((phase) => <td key={phase}>{report.comparacion[phase][key].valor ?? 'Sin datos'}<br /><small>{report.comparacion[phase][key].numerador} / {report.comparacion[phase][key].denominador}</small></td>)}<td>{report.comparacion.diferencias[key] ?? 'Sin datos'}</td></tr>)}</tbody></table></div>
      <p>{report.comparacion.muestras_sin_par} muestras sin condiciones equivalentes en la otra fase. {report.comparacion.limitacion}</p>
      <details><summary>Condiciones incluidas en la comparación</summary><ul>{report.comparacion.condiciones_comparables.map((item) => <li key={`${item.turno}-${item.modalidad}-${item.condiciones}`}>{item.turno} · {item.modalidad} · {item.condiciones}</li>)}</ul></details>
      <div className="ops-actions"><a className="ops-link" href={`/api/admin/indicators/export?${query}`}>Descargar base anónima CSV</a></div>
      <div className="ops-table-wrap"><table><caption>Base de observaciones</caption><thead><tr><th>Muestra</th><th>Condiciones</th><th>Datos observados</th><th>Limitaciones y exclusión</th></tr></thead><tbody>{report.mediciones.map((row) => <tr key={row.id}><td>{row.codigo}<br />{row.fecha} · {row.fase}</td><td>{row.turno} · {row.modalidad}<p>{row.condiciones}</p></td><td>{row.errores} errores y {row.completos} completos / {row.pedidos} pedidos<br />{row.minutos_totales} min / {row.pedidos_cronometrados} cronometrados<br />{row.insumos_exactos} exactos / {row.insumos_revisados} insumos</td><td><p>{row.limitaciones || 'Sin limitaciones registradas.'}</p><p>{row.excluida ? 'Excluida' : 'Incluida'}{row.motivo_exclusion && ` · ${row.motivo_exclusion}`}</p><form onSubmit={(e) => { e.preventDefault(); action.run(() => apiJson(`/api/admin/indicators/${row.id}/exclusion`, { method: 'PATCH', body: { excluida: !row.excluida, motivo_exclusion: reasons[row.id] || '' } })) }}><label>Motivo del cambio<input required maxLength={500} value={reasons[row.id] || ''} onChange={(e) => setReasons({ ...reasons, [row.id]: e.target.value })} /></label><button disabled={action.busy}>{row.excluida ? 'Volver a incluir' : 'Excluir'}</button></form></td></tr>)}</tbody></table></div>
      <Pagination page={page} total={report.total} onChange={setPage} />
    </>}
  </>
}

export default function OperationsPanel({ section }) {
  const View = { Personal: Staff, Auditoría: Audit, Respaldos: Backups, Piloto: Pilot, Indicadores: Indicators, Recetas: RecipeEditor, Reportes: OrderReport }[section]
  return <section className="ops-panel" aria-label={section}><View /></section>
}
