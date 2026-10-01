import './threejs-override.js'
import './style/index.styl'
import shellHtml from './shell.html?raw'
import { Game } from './Game/Game.js'

/**
 * Mount Bruno folio Game into a Vue host element.
 * @param {HTMLElement} host
 * @param {{ onNavigate?: (def: { route: string, perm?: string, title?: string }) => void, getAuth?: () => { user: any, hasPerm: (p: string) => boolean } }} options
 */
export function mountFolio(host, options = {}) {
  if (!host) throw new Error('mountFolio: host element required')

  host.innerHTML = shellHtml
  const root = host.querySelector('.game')
  if (!root) throw new Error('mountFolio: .game root missing from shell')

  const fontsLinkId = 'folio-google-fonts'
  if (!document.getElementById(fontsLinkId)) {
    const pre1 = document.createElement('link')
    pre1.rel = 'preconnect'
    pre1.href = 'https://fonts.googleapis.com'
    document.head.appendChild(pre1)
    const pre2 = document.createElement('link')
    pre2.rel = 'preconnect'
    pre2.href = 'https://fonts.gstatic.com'
    pre2.crossOrigin = ''
    document.head.appendChild(pre2)
    const link = document.createElement('link')
    link.id = fontsLinkId
    link.rel = 'stylesheet'
    link.href =
      'https://fonts.googleapis.com/css2?family=Amatic+SC:wght@700&family=Nunito:wght@400;700;900&display=block'
    document.head.appendChild(link)
  }

  const museBridge = {
    navigate(def) {
      if (typeof options.onNavigate === 'function') {
        options.onNavigate(def)
        return
      }
      const auth = typeof options.getAuth === 'function' ? options.getAuth() : null
      if (!auth?.user) {
        window.location.href = `/login?next=${encodeURIComponent(def.route)}`
        return
      }
      if (def.perm && auth.hasPerm && !auth.hasPerm(def.perm)) {
        Game.getInstance()?.notifications?.show(`没有权限进入「${def.title || def.route}」`, 'danger', 4)
        return
      }
      window.location.href = def.route
    },
  }

  const game = new Game({ root, museBridge })

  return {
    game,
    destroy() {
      try {
        game.destroy()
      } catch (err) {
        console.warn('mountFolio destroy', err)
      }
      host.innerHTML = ''
    },
  }
}
