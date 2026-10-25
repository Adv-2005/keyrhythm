import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import Enrollment from './Enrollment'
import { CHALLENGE } from './timing'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('requires consent and sends only aligned timing data for a completed challenge', async () => {
  const requests: { url: string; body?: string }[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    requests.push({ url, body: init?.body as string | undefined })
    if (url.endsWith('/profiles') && init?.method === 'POST') {
      return { ok: true, status: 201, json: async () => ({ id: 1, display_name: 'P1', sample_count: 0, enrollment_target: 10, enrollment_status: 'collecting' }) }
    }
    if (url.endsWith('/samples')) {
      return { ok: true, status: 201, json: async () => ({ id: 1, profile_id: 1, sample_count: 1 }) }
    }
    return { ok: true, status: 200, json: async () => [] }
  }))

  render(<Enrollment />)
  fireEvent.change(screen.getByRole('textbox', { name: 'New profile label' }), { target: { value: 'P1' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create profile' }))
  await waitFor(() => expect(screen.getByRole('checkbox').hasAttribute('disabled')).toBe(false))
  expect(screen.getByRole('textbox', { name: 'Type the sentence exactly' }).hasAttribute('disabled')).toBe(true)
  fireEvent.click(screen.getByRole('checkbox'))
  const input = screen.getByRole('textbox', { name: 'Type the sentence exactly' })
  expect(input.hasAttribute('disabled')).toBe(false)

  let typed = ''
  for (let i = 0; i < CHALLENGE.length; i++) {
    const key = CHALLENGE[i]
    const code = `pos-${i}`
    const down = new KeyboardEvent('keydown', { bubbles: true, key, code })
    Object.defineProperty(down, 'timeStamp', { value: 100 + i * 150 })
    fireEvent(input, down)
    typed += key
    fireEvent.change(input, { target: { value: typed } })
    const up = new KeyboardEvent('keyup', { bubbles: true, key, code })
    Object.defineProperty(up, 'timeStamp', { value: 180 + i * 150 })
    fireEvent(input, up)
  }

  const save = screen.getByRole('button', { name: 'Save sample' })
  expect(save.hasAttribute('disabled')).toBe(false)
  fireEvent.click(save)
  await waitFor(() => expect(requests.some((request) => request.url.endsWith('/samples'))).toBe(true))
  const body = JSON.parse(requests.find((request) => request.url.endsWith('/samples'))!.body!)
  expect(body.consent_acknowledged).toBe(true)
  expect(body.timing_sequence.hold_ms).toHaveLength(CHALLENGE.length)
  expect(JSON.stringify(body)).not.toContain(CHALLENGE)
  expect(body).not.toHaveProperty('typed_text')
  expect(body.timing_sequence).not.toHaveProperty('keys')
  await waitFor(() => expect(screen.getByText(/1 \/ 10 samples/)).toBeTruthy())

  fireEvent.change(screen.getByRole('textbox', { name: 'New profile label' }), { target: { value: 'P2' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create profile' }))
  await waitFor(() => expect(screen.getByRole('checkbox').hasAttribute('checked')).toBe(false))
  expect(screen.getByRole('textbox', { name: 'Type the sentence exactly' }).hasAttribute('disabled')).toBe(true)
})
