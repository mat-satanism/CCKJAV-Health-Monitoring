import type { CollectedBy } from './types'

/** Who provides each value, in the words the app shows (backend/app/config.py, docs/data-entry.md). */
export const COLLECTED_BY: Record<CollectedBy, string> = {
  device: 'from the wearable',
  test: 'from the 3-minute test',
  medic: 'measured by the medic',
  self: 'your own answer',
}
