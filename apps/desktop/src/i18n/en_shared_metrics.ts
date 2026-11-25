import type { Translations } from './types'

export const enSharedMetrics: Translations['sharedMetrics'] = {
  consentTitle: 'Collect usage stats locally?',
  dialogTitle: 'Usage stats',
  consentBody:
    'Nara can count how you use it: session length, which models and tools run, and when something fails. It never records your messages, files, paths or error text.',
  whatIsCollected: 'What is counted',
  collectedActivity: 'Sessions: length, outcome, error type, active time per day',
  collectedModels: 'Models: which ones, token totals',
  collectedNames: 'Features: built-in tools, commands, app areas and settings used or turned off',
  collectedMilestones: 'Setup: which steps finished, provider connections, how many skills, plugins and jobs',
  collectedReliability: 'App health: crashes, startup and reply speed, updates, messaging connections',
  collectedUsage: 'Agent quality: missed edits, broken tool calls, stuck loops, cost per task',
  collectedMachine: 'Machine: OS, RAM range, GPU type, Nara version, local model use',
  sending:
    'This choice stores counters on this device and sends nothing. Sending requires a separate endpoint and send setting in config.yaml. Change local collection anytime in Settings.',
  readDocs: 'Read the full details',
  share: 'Collect locally',
  off: 'No thanks',
  saveFailed: 'Couldn’t save your choice',
  sendLabel: 'Collect usage stats on this device',
  sendDesc:
    'Stores counters locally. Sends nothing. Never records your messages, files, paths or error text.',
  unavailable: 'Update the Nara backend to change this setting.',
  stripBody: 'Counts only. Never your messages or files.',
  stripReaskBody: 'Asking once more: an earlier version could save “No thanks” before you saw this.',
  stripChoices: { share: 'Collect locally', off: 'No thanks' },
  stripDetails: 'Details'
}
