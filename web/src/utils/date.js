/** 本地时区 YYYY-MM-DD（toISOString 是 UTC，北京时间 0-8 点会差一天） */
export function fmtDateLocal(d) {
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** 今天（本地） */
export function todayLocal() {
  return fmtDateLocal(new Date())
}

/** N 年前的今天（本地） */
export function yearsAgoLocal(n) {
  const d = new Date()
  d.setFullYear(d.getFullYear() - n)
  return fmtDateLocal(d)
}
