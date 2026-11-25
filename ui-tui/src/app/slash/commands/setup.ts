import { withInkSuspended } from '@nara/ink'

import { t } from '../../../i18n/runtime.js'
import { launchNaraCommand } from '../../../lib/externalCli.js'
import { runExternalSetup } from '../../setupHandoff.js'
import type { SlashCommand } from '../types.js'

export const setupCommands: SlashCommand[] = [
  {
    help: 'run full setup wizard (launches `nara setup`)',
    name: 'setup',
    run: (arg, ctx) =>
      void runExternalSetup({
        args: ['setup', ...arg.split(/\s+/).filter(Boolean)],
        ctx,
        done: t('slashCmd.setup.setup.done'),
        launcher: launchNaraCommand,
        suspend: withInkSuspended
      })
  }
]
