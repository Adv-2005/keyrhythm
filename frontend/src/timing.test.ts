import { describe, expect, it } from 'vitest'
import { CHALLENGE, TimingCapture } from './timing'

function validCapture() {
  const capture = new TimingCapture()
  let typed = ''
  for (let i = 0; i < CHALLENGE.length; i++) {
    const key = CHALLENGE[i]
    const code = `position-${i}`
    capture.keyDown(key, code, 100 + i * 150, false, false)
    typed += key
    capture.checkInput(typed)
    capture.keyUp(key, code, 180 + i * 150)
  }
  return capture
}

describe('field-scoped timing capture', () => {
  it('produces aligned numeric sequences without key values', () => {
    const sequence = validCapture().complete(CHALLENGE)
    expect(sequence?.hold_ms).toHaveLength(CHALLENGE.length)
    expect(sequence?.down_down_ms).toHaveLength(CHALLENGE.length - 1)
    expect(sequence?.flight_ms[0]).toBe(70)
    expect(sequence?.total_ms).toBe(150 * (CHALLENGE.length - 1) + 80)
    expect(JSON.stringify(sequence)).not.toContain(CHALLENGE)
    expect(Object.keys(sequence!)).toEqual(['hold_ms', 'down_down_ms', 'flight_ms', 'long_pauses', 'total_ms'])
  })

  it('rejects repeats, corrections, missing releases, and changed text', () => {
    const repeated = new TimingCapture()
    repeated.keyDown(CHALLENGE[0], 'KeyT', 100, true, false)
    expect(repeated.complete(CHALLENGE)).toBeNull()
    expect(repeated.error).toBeTruthy()

    const corrected = new TimingCapture()
    corrected.keyDown(CHALLENGE[0], 'KeyT', 100, false, false)
    corrected.checkInput('wrong')
    expect(corrected.error).toBeTruthy()

    const missing = new TimingCapture()
    missing.keyDown(CHALLENGE[0], 'KeyT', 100, false, false)
    missing.keyUp(CHALLENGE[0], 'Other', 180)
    expect(missing.error).toBeTruthy()
  })

  it('accepts overlapping key holds with signed flight intervals', () => {
    const capture = new TimingCapture()
    let typed = ''
    for (let i = 0; i < CHALLENGE.length; i++) {
      const key = CHALLENGE[i]
      capture.keyDown(key, `code-${i}`, 100 + i * 50, false, false)
      typed += key
      capture.checkInput(typed)
      capture.keyUp(key, `code-${i}`, 180 + i * 50)
    }
    expect(capture.complete(CHALLENGE)?.flight_ms[0]).toBe(-30)
  })
})
