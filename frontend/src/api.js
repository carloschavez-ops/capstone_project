// Un token de formulario por sesión. Una petición CSRF rechazada aún no mutó datos.
let tokenRequest = null

async function csrfToken() {
  if (!tokenRequest) {
    tokenRequest = window.fetch('/api/auth/csrf', { credentials: 'same-origin' })
      .then(async (response) => {
        if (!response.ok) throw new Error('No se pudo proteger el formulario. Recarga la página.')
        return (await response.json()).csrf_token
      })
      .finally(() => { tokenRequest = null })
  }
  return tokenRequest
}

export async function apiFetch(url, options = {}) {
  function checkSession(response) {
    if (response.status === 401 && url !== '/api/auth/login') window.dispatchEvent(new Event('pizza-session-expired'))
    return response
  }
  const write = ['POST', 'PUT', 'PATCH', 'DELETE'].includes((options.method || 'GET').toUpperCase())
  if (!write) return checkSession(await window.fetch(url, { credentials: 'same-origin', ...options }))
  const send = async () => {
    const headers = new Headers(options.headers)
    headers.set('X-CSRF-Token', await csrfToken())
    return window.fetch(url, { credentials: 'same-origin', ...options, headers })
  }
  let response = await send()
  if (response.status === 403) {
    const result = await response.clone().json().catch(() => ({}))
    if (result.code === 'csrf_invalid') response = await send()
  }
  return checkSession(response)
}

export async function apiJson(url, options = {}) {
  const response = await apiFetch(url, options.body && !(options.body instanceof FormData)
    ? { ...options, headers: { 'Content-Type': 'application/json', ...options.headers }, body: JSON.stringify(options.body) }
    : options)
  const result = await response.json()
  if (!response.ok) throw new Error(result.error || 'No se pudo completar la operación.')
  return result
}
