import client from './client'

/** Get industry sector strength ranking */
export function getSectorRanking(forceRefresh = false, topN = 10) {
  return client.get('/sectors/ranking', { params: { force_refresh: forceRefresh, top_n: topN } })
}

/** Get stocks within a sector (optionally screened) */
export function getSectorStocks(sectorCode, screened = true, limit = 30) {
  return client.get(`/sectors/${sectorCode}/stocks`, { params: { screened, limit } })
}

/** Get blacklisted weak sectors */
export function getBlacklistedSectors() {
  return client.get('/sectors/blacklist/view')
}

/** Get best screened stocks from top-N bullish sectors */
export function getTopSectorStocks(topN = 10, stocksPerSector = 10) {
  return client.get('/sectors/top-stocks', { params: { top_n: topN, stocks_per_sector: stocksPerSector } })
}

/** Get sector K-line data */
export function getSectorKline(sectorCode, count = 80) {
  return client.get('/market/sector-kline', { params: { sector_code: sectorCode, count } })
}
