/** Timing schema timing-1: milliseconds, aligned to fixed-1 challenge positions. */
export const CHALLENGE = 'the quick brown fox jumps over the lazy dog.'
export const CHALLENGE_VERSION = 'fixed-1'
export const FEATURE_VERSION = 'timing-1'
export const PAUSE_THRESHOLD_MS = 750

export type TimingSequence = {
  hold_ms: number[]
  down_down_ms: number[]
  flight_ms: number[]
  long_pauses: boolean[]
  total_ms: number
}

type Press = { position: number; down: number }

/** Holds only transient key identifiers until key-up; exports numeric timing only. */
export class TimingCapture {
  private downs: number[] = []
  private ups: number[] = []
  private active = new Map<string, Press>()
  error: string | null = null

  invalidate(message: string) {
    this.error = message
    this.active.clear()
    this.downs = []
    this.ups = []
  }

  keyDown(key: string, code: string, time: number, repeat: boolean, modified: boolean) {
    if (this.error) return
    if (key === 'Shift' || key === 'Control' || key === 'Alt' || key === 'Meta') return
    if (repeat || modified || key.length !== 1 || this.downs.length >= CHALLENGE.length ||
        key !== CHALLENGE[this.downs.length] || this.active.has(code)) {
      this.invalidate('Typing changed or used an unsupported key. Restart this sample.')
      return
    }
    this.active.set(code, { position: this.downs.length, down: time })
    this.downs.push(time)
  }

  keyUp(key: string, code: string, time: number) {
    if (this.error || key.length !== 1) return
    const press = this.active.get(code)
    if (!press || time <= press.down) {
      this.invalidate('A key release was missing or invalid. Restart this sample.')
      return
    }
    this.ups[press.position] = time
    this.active.delete(code)
  }

  checkInput(value: string) {
    if (!this.error && (value.length !== this.downs.length || !CHALLENGE.startsWith(value))) {
      this.invalidate('The challenge was changed. Restart this sample.')
    }
  }

  complete(value: string): TimingSequence | null {
    if (this.error || value !== CHALLENGE || this.downs.length !== CHALLENGE.length ||
        this.ups.length !== CHALLENGE.length || Array.from({ length: CHALLENGE.length }, (_, i) => this.ups[i]).some((up) => up === undefined) ||
        this.active.size !== 0) return null

    const round = (value: number) => Math.round(value * 1000) / 1000
    const hold_ms = this.downs.map((down, i) => round(this.ups[i] - down))
    const down_down_ms = this.downs.slice(1).map((down, i) => round(down - this.downs[i]))
    const flight_ms = this.downs.slice(1).map((down, i) => round(down - this.ups[i]))
    const total_ms = round(this.ups.at(-1)! - this.downs[0])
    if (hold_ms.some((n) => !Number.isFinite(n) || n <= 0 || n > 5000) ||
        down_down_ms.some((n) => !Number.isFinite(n) || n <= 0 || n > 10000) ||
        flight_ms.some((n) => !Number.isFinite(n) || n < -5000 || n > 10000) ||
        !Number.isFinite(total_ms) || total_ms <= 0 || total_ms > 120000) {
      this.invalidate('Timing was outside the accepted range. Restart this sample.')
      return null
    }
    return { hold_ms, down_down_ms, flight_ms,
      long_pauses: flight_ms.map((gap) => gap >= PAUSE_THRESHOLD_MS), total_ms }
  }
}
