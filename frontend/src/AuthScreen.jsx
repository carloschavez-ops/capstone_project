import { useState } from 'react'
import { ArrowRight, UserRound } from 'lucide-react'

export default function AuthScreen({ mode, onModeChange, onSubmit, onGuest, busy, error }) {
  const [values, setValues] = useState({ nombre: '', email: '', password: '', confirmPassword: '' })
  const [validationError, setValidationError] = useState('')
  const isRegister = mode === 'register'

  function update(field, value) {
    setValues((current) => ({ ...current, [field]: value }))
    setValidationError('')
  }

  function submit(event) {
    event.preventDefault()
    if (isRegister && values.password !== values.confirmPassword) {
      setValidationError('Las contraseñas no coinciden.')
      return
    }
    onSubmit(mode, values)
  }

  return (
    <main className="auth-shell">
      <section className="auth-story">
        <a className="brand auth-brand" href="#inicio" aria-label="Pizza Pronto">
          <span className="brand-mark">P</span><span>pizza<span className="brand-light">pronto</span></span>
        </a>
        <div className="auth-story-copy">
          <p className="eyebrow"><span className="live-dot" /> HORNO ENCENDIDO · BAÑOS DEL INCA</p>
          <h1>La mesa<br />ya está <em>lista.</em></h1>
          <p>Masa lenta, ingredientes honestos y una pizza para compartir.</p>
        </div>
        <span className="auth-story-caption">HECHA CON CALMA · SERVIDA CALIENTE</span>
      </section>

      <section className="auth-side">
        <div className="auth-mobile-brand"><span className="brand-mark">P</span><span>pizza<span className="brand-light">pronto</span></span></div>
        <div className="auth-box">
          <p className="eyebrow">BIENVENIDO A PIZZA PRONTO</p>
          <h2>{isRegister ? 'Crea tu cuenta.' : 'Qué bueno verte.'}</h2>
          <p className="auth-intro">{isRegister ? 'Tus próximas pizzas empiezan aquí.' : 'Entra a tu cuenta o pide como invitado.'}</p>

          <div className="auth-tabs" role="tablist" aria-label="Acceso">
            <button className={!isRegister ? 'active' : ''} onClick={() => onModeChange('login')} role="tab" aria-selected={!isRegister}>Iniciar sesión</button>
            <button className={isRegister ? 'active' : ''} onClick={() => onModeChange('register')} role="tab" aria-selected={isRegister}>Crear cuenta</button>
          </div>

          <form className="auth-form" onSubmit={submit}>
            {isRegister && <label>Nombre completo<input autoComplete="name" required maxLength={120} value={values.nombre} onChange={(event) => update('nombre', event.target.value)} /></label>}
            <label>Correo electrónico<input type="email" autoComplete="email" required maxLength={254} value={values.email} onChange={(event) => update('email', event.target.value)} /></label>
            <label>Contraseña<input type="password" autoComplete={isRegister ? 'new-password' : 'current-password'} required minLength={isRegister ? 8 : 1} value={values.password} onChange={(event) => update('password', event.target.value)} /></label>
            {isRegister && <label>Repite la contraseña<input type="password" autoComplete="new-password" required minLength={8} value={values.confirmPassword} onChange={(event) => update('confirmPassword', event.target.value)} /></label>}
            {(error || validationError) && <p className="auth-error" role="alert">{validationError || error}</p>}
            <button className="primary-button auth-submit" disabled={busy}>
              {busy ? 'Un momento...' : isRegister ? 'Crear cuenta' : 'Entrar'} <ArrowRight size={17} />
            </button>
          </form>

          <div className="auth-divider"><span>O</span></div>
          <button className="guest-button" onClick={onGuest} disabled={busy}><UserRound size={17} /> Continuar como invitado</button>
        </div>
        <p className="auth-footnote">HECHO AL MOMENTO · BAÑOS DEL INCA, PERÚ</p>
      </section>
    </main>
  )
}