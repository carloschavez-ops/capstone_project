import { useEffect } from 'react'

// Gestiona también los diálogos anidados del panel y conserva el foco del disparador.
export default function DialogAccessibility() {
  useEffect(() => {
    const root = document.getElementById('root')
    let active = null
    let restoreFocus = null
    let inertNodes = []
    const previousOverflow = document.body.style.overflow
    const candidates = () => active ? [...active.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')].filter((node) => node.getClientRects().length) : []
    function restoreBackground() {
      inertNodes.forEach(([node, previous]) => { node.inert = previous })
      inertNodes = []
      document.body.style.overflow = previousOverflow
    }
    function sync() {
      const dialogs = [...root.querySelectorAll('[role="dialog"][aria-modal="true"]')]
      const next = dialogs.at(-1) || null
      if (next === active) return
      restoreBackground()
      if (!active) restoreFocus = document.activeElement
      active = next
      if (!next) {
        if (restoreFocus?.isConnected) restoreFocus.focus()
        return
      }
      let child = next
      while (child.parentElement && child !== root) {
        for (const sibling of child.parentElement.children) {
          if (sibling !== child) { inertNodes.push([sibling, sibling.inert]); sibling.inert = true }
        }
        child = child.parentElement
      }
      document.body.style.overflow = 'hidden'
      next.tabIndex = -1
      ;(candidates()[0] || next).focus()
    }
    function keydown(event) {
      if (!active) return
      if (event.key === 'Escape') {
        const close = active.querySelector('button[aria-label^="Cerrar"]')
        if (close) { event.preventDefault(); close.click() }
      } else if (event.key === 'Tab') {
        const elements = candidates()
        const first = elements[0], last = elements.at(-1)
        if (!first) { event.preventDefault(); active.focus() }
        else if (!active.contains(document.activeElement)) { event.preventDefault(); (event.shiftKey ? last : first).focus() }
        else if (event.shiftKey && (document.activeElement === first || document.activeElement === active)) { event.preventDefault(); last.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
      }
    }
    const observer = new MutationObserver(sync)
    observer.observe(root, { childList: true, subtree: true })
    document.addEventListener('keydown', keydown)
    sync()
    return () => { observer.disconnect(); document.removeEventListener('keydown', keydown); restoreBackground() }
  }, [])
  return null
}
