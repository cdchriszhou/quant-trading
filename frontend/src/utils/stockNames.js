/**
 * Stock code → Chinese name lookup.
 * Only stores names resolved from live market APIs — no hardcoded catalog.
 */
import { marketApi } from '@/api/market'
import { ref } from 'vue'

/** Runtime map filled only by API responses */
const map = Object.create(null)
/** bump to trigger Vue re-render after async name fills */
export const stockNameVersion = ref(0)

function _normalize(code) {
  if (!code) return ''
  return String(code).trim().toUpperCase()
}

function _bare(code) {
  return _normalize(code).replace(/\.(SZ|SH|BJ)$/i, '')
}

function _remember(code, name) {
  if (!code || !name) return
  const full = _normalize(code)
  const bare = _bare(full)
  map[full] = name
  map[bare] = name
  if (!full.includes('.')) {
    if (/^(6|9)/.test(bare)) map[`${bare}.SH`] = name
    else map[`${bare}.SZ`] = name
  }
  stockNameVersion.value += 1
}

/** Enhance with real-time API data (non-blocking). */
export async function initStockNames() {
  try {
    const res = await marketApi.searchSymbols('')
    const list = res.data || []
    list.forEach((s) => {
      if (s?.code && s?.name) _remember(s.code, s.name)
    })
    console.log(`[stockNames] Loaded ${list.length} names from live API`)
  } catch (e) {
    console.warn('[stockNames] API load failed (no builtin fallback):', e.message || e)
  }
}

/**
 * Synchronous lookup. Prefer row.symbol_name from API when available.
 * Never invents a Chinese name for an unknown code.
 */
export function getStockName(code, fallbackName = '') {
  void stockNameVersion.value
  if (fallbackName && fallbackName !== code && fallbackName !== _bare(code)) {
    return fallbackName
  }
  if (!code) return ''
  const full = _normalize(code)
  const bare = _bare(full)
  const name = map[full] || map[bare] || map[`${bare}.SZ`] || map[`${bare}.SH`] || ''
  if (!name || name === full || name === bare) return ''
  return name
}

/** Display helper for table rows that may already carry symbol_name. */
export function displayStockName(rowOrCode, maybeCode) {
  if (rowOrCode && typeof rowOrCode === 'object') {
    const sym = rowOrCode.symbol || maybeCode
    return getStockName(sym, rowOrCode.symbol_name || rowOrCode.name)
  }
  return getStockName(rowOrCode)
}

/** Fetch missing names via market search (best-effort). */
export async function ensureStockNames(codes = []) {
  const uniq = [...new Set((codes || []).filter(Boolean).map(_normalize))]
  const missing = uniq.filter((c) => !getStockName(c))
  if (!missing.length) return
  await Promise.all(
    missing.map(async (code) => {
      try {
        const q = _bare(code)
        const res = await marketApi.searchSymbols(q)
        const list = res.data || []
        const hit = list.find((s) => _normalize(s.code) === code)
          || list.find((s) => _bare(s.code) === q)
          || list[0]
        if (hit?.name) _remember(code, hit.name)
      } catch {
        /* ignore */
      }
    }),
  )
}
