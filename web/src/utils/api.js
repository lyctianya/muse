/* 统一 API 封装：自动携带 Cookie（登录态） */
export async function apiFetch(url, opts = {}) {
  const res = await fetch(url, { credentials: 'include', ...opts })
  if (res.status === 401) {
    if (!location.pathname.startsWith('/login')) {
      location.href = '/login?next=' + encodeURIComponent(location.pathname + location.search)
    }
    throw new Error('未登录或登录已过期')
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const text = await res.text()
      msg = JSON.parse(text).detail || msg
    } catch { /* ignore */ }
    const err = new Error(msg)
    err.status = res.status
    throw err
  }
  return res
}

export async function getJSON(url) {
  return (await apiFetch(url)).json()
}

export async function postJSON(url, body) {
  return (await apiFetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })).json()
}

export async function putJSON(url, body) {
  return (await apiFetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })).json()
}

export async function del(url) {
  return (await apiFetch(url, { method: 'DELETE' })).json()
}
