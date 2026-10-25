import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('dashboard foundation', () => {
  it('shows backend connectivity from the health endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    expect(await screen.findByText('API connected')).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/health', expect.objectContaining({ signal: expect.any(AbortSignal) }))
  })

  it('shows an unavailable state when the backend cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))

    render(<App />)

    expect(await screen.findByText('API unavailable')).toBeTruthy()
  })

  it('navigates to enrolment and baseline verification', () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise(() => {})))
    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Enrolment' }))

    expect(screen.getByRole('heading', { name: 'Typing enrolment' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Authentication' }))
    expect(screen.getByRole('heading', { name: 'Verify typing rhythm' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Model laboratory' }))
    expect(screen.getByRole('heading', { name: 'Siamese CNN' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Evaluation' }))
    expect(screen.getByRole('heading', { name: 'Held-out verification experiment' })).toBeTruthy()
  })
})
