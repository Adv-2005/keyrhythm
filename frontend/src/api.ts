export type HealthResponse = { status: 'ok' }

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl}/health`, { signal })
  if (!response.ok) {
    throw new Error(`Health request failed (${response.status})`)
  }

  const data: unknown = await response.json()
  if (!data || typeof data !== 'object' || !('status' in data) || data.status !== 'ok') {
    throw new Error('Unexpected health response')
  }
  return { status: 'ok' }
}
