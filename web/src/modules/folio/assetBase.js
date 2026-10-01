/** Static assets live under Vite public/folio → served at /folio/ */
export const FOLIO_ASSET_BASE = '/folio/'

export function folioAsset(path) {
  if (!path || typeof path !== 'string') return path
  if (
    path.startsWith('http://') ||
    path.startsWith('https://') ||
    path.startsWith('data:') ||
    path.startsWith('blob:') ||
    path.startsWith(FOLIO_ASSET_BASE) ||
    path.startsWith('/')
  ) {
    return path
  }
  return FOLIO_ASSET_BASE + path.replace(/^\.\//, '')
}
