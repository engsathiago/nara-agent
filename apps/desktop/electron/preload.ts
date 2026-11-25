import { contextBridge, ipcRenderer, webFrame, webUtils } from 'electron'

import type { DesktopProfileRoute } from './desktop-profile'
import type { HudModifierApi, HudModifierStatus } from './hud-modifier-types'
import { customWindowControlsEnabled } from './window-controls'

// Which translucency the OS can back. Asked synchronously because the renderer
// needs it before its first paint, and answered by main because deciding it
// needs `os.release()` — a sandboxed preload may only require electron, events,
// timers and url, so importing node:os here throws before contextBridge runs
// and takes the ENTIRE bridge down with it (window.naraDesktop undefined =>
// "Desktop IPC bridge is unavailable"). No reply means no glass, which degrades
// to an ordinary opaque window rather than a page thinned over nothing.
const translucencySupport = ipcRenderer.sendSync('nara:translucency:support')
const hudWindowing = ipcRenderer.sendSync('nara:hud:windowing')
const hudNativeDrag = hudWindowing?.nativeDrag === true

const launchFlags: { localModels?: boolean; assumeFreshInstall?: boolean } | undefined =
  ipcRenderer.sendSync('nara:feature-flags')

// Local, sanitized skin payload for the first renderer theme paint. This does
// not wait on `gateway.ready`, so an unreachable remote primary cannot force
// the built-in palette over the skin configured on this machine.
const localSkin = ipcRenderer.sendSync('nara:skin:local')

// This machine's UI preferences store (#145213), read before the first paint so
// a preference set in another window or in this machine's Webapp paints at once.
const uiPreferencesSnapshot = ipcRenderer.sendSync('nara:ui-preferences:snapshot')

import { unwrapExpectedNotFound } from './api-expected-404'

contextBridge.exposeInMainWorld('naraDesktop', {
  glassSupported: translucencySupport?.glass === true,
  translucencySupported: translucencySupport?.translucency === true,
  // Launch-flag fact: the app was started with --local, so the renderer may
  // show the local-models surfaces. Static for the window's lifetime.
  localModelsEnabled: launchFlags?.localModels === true,
  // Dev-only launch fact: an unpackaged app started with --fresh-install, so
  // onboarding treats this launch as a fresh install. Always false when packaged.
  assumeFreshInstall: launchFlags?.assumeFreshInstall === true,
  localSkin: localSkin && typeof localSkin === 'object' ? localSkin : null,
  uiPreferences: {
    snapshot: uiPreferencesSnapshot && typeof uiPreferencesSnapshot === 'object' ? uiPreferencesSnapshot : null,
    read: () => ipcRenderer.invoke('nara:ui-preferences:read'),
    write: payload => ipcRenderer.invoke('nara:ui-preferences:write', payload),
    onChanged: callback => {
      const listener = (_event, snapshot) => callback(snapshot)
      ipcRenderer.on('nara:ui-preferences:changed', listener)

      return () => ipcRenderer.removeListener('nara:ui-preferences:changed', listener)
    }
  },
  getConnection: (profile, opts) => ipcRenderer.invoke('nara:connection', profile, opts),
  // Loopback origin that hosts YouTube's player for the file:// renderer.
  getEmbedHostOrigin: () => ipcRenderer.invoke('nara:embed-host:origin'),
  // Registry-scoped backend resolution: { connectionId, profile } → descriptor.
  getConnectionFor: payload => ipcRenderer.invoke('nara:connection:for', payload),
  getProfileRoutes: profiles => ipcRenderer.invoke('nara:plugin-profile-routes', profiles),
  revalidateConnection: () => ipcRenderer.invoke('nara:connection:revalidate'),
  getGatewayWsUrl: profile => ipcRenderer.invoke('nara:gateway:ws-url', profile),
  // Registry-scoped fresh WS URL: { connectionId, profile } → result shape of
  // getGatewayWsUrl, minted against that connection's backend.
  getGatewayWsUrlFor: payload => ipcRenderer.invoke('nara:gateway:ws-url-for', payload),
  // { connectionId, profile, pluginId, path } → one-use local plugin socket URL, null, or { refused: 'permission' }.
  getPluginWsUrl: payload => ipcRenderer.invoke('nara:plugin:ws-url', payload),
  // Union agent roster across every registered connection.
  getAgentRoster: () => ipcRenderer.invoke('nara:agents:roster'),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('nara:window:openSession', sessionId, opts),
  openSessionInTerminal: (sessionId, opts) => ipcRenderer.invoke('nara:window:openInTerminal', sessionId, opts),
  openWindow: (options?: DesktopProfileRoute) => ipcRenderer.invoke('nara:window:openInstance', options),
  openBrowserWindow: tabId => ipcRenderer.invoke('nara:window:openBrowser', tabId),
  windowRelay: {
    send: payload => ipcRenderer.send('nara:window:relay', payload),
    onMessage: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('nara:window:relay', listener)

      return () => ipcRenderer.removeListener('nara:window:relay', listener)
    }
  },
  onBrowserPopoutClosed: callback => {
    const listener = (_event, tabId) => callback(tabId)
    ipcRenderer.on('nara:browser-popout:closed', listener)

    return () => ipcRenderer.removeListener('nara:browser-popout:closed', listener)
  },
  claimAmbientCue: key => ipcRenderer.invoke('nara:ambient:claim', key),
  windowControls: {
    custom: customWindowControlsEnabled(),
    minimize: () => ipcRenderer.send('nara:window-control', 'minimize'),
    toggleMaximize: () => ipcRenderer.send('nara:window-control', 'toggle-maximize'),
    close: () => ipcRenderer.send('nara:window-control', 'close')
  },
  wakeIndicator: {
    getState: () => ipcRenderer.invoke('nara:wake-indicator:get'),
    setState: state => ipcRenderer.send('nara:wake-indicator:set', state),
    onState: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('nara:wake-indicator:state', listener)

      return () => ipcRenderer.removeListener('nara:wake-indicator:state', listener)
    }
  },
  chatOnboarding: {
    size: mode => ipcRenderer.send('nara:window:size', mode)
  },
  petOverlay: {
    // Main renderer → main process: window lifecycle + drag. `request` is
    // `{ bounds, screen }`; resolves with the screen bounds it actually used.
    open: request => ipcRenderer.invoke('nara:pet-overlay:open', request),
    close: () => ipcRenderer.invoke('nara:pet-overlay:close'),
    setBounds: bounds => ipcRenderer.send('nara:pet-overlay:set-bounds', bounds),
    setIgnoreMouse: ignore => ipcRenderer.send('nara:pet-overlay:ignore-mouse', ignore),
    // Flip the overlay focusable (and focus it) while the composer needs keys.
    setFocusable: focusable => ipcRenderer.send('nara:pet-overlay:set-focusable', focusable),
    // Main renderer → overlay (forwarded by main): push the latest pet state.
    pushState: payload => ipcRenderer.send('nara:pet-overlay:state', payload),
    // Overlay → main renderer (forwarded by main): pop back in / composer submit.
    control: payload => ipcRenderer.send('nara:pet-overlay:control', payload),
    // Overlay subscribes to state pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('nara:pet-overlay:state', listener)

      return () => ipcRenderer.removeListener('nara:pet-overlay:state', listener)
    },
    // Main renderer subscribes to overlay control messages.
    onControl: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('nara:pet-overlay:control', listener)

      return () => ipcRenderer.removeListener('nara:pet-overlay:control', listener)
    }
  },
  // HUD mode: the chrome-free floating chat. A full app renderer (own gateway)
  // sized as a floating bar, so it mounts the real composer. Main owns the
  // window; `onChanged` keeps every window's toggle truthful.
  hud: {
    nativeDrag: hudNativeDrag,
    windowing: {
      clientPlacement: hudWindowing?.clientPlacement !== false,
      controlDrag: hudWindowing?.controlDrag === true,
      nativeDrag: hudNativeDrag,
      solid: hudWindowing?.solid === true,
      workspaceTransfer: hudWindowing?.workspaceTransfer === true
    },
    open: request => ipcRenderer.invoke('nara:hud:open', request),
    close: () => ipcRenderer.invoke('nara:hud:close'),
    setIgnoreMouse: ignore => ipcRenderer.send('nara:hud:ignore-mouse', ignore),
    beginMove: () => ipcRenderer.send('nara:hud:begin-move'),
    endMove: () => ipcRenderer.send('nara:hud:end-move'),
    moveBy: delta => ipcRenderer.send('nara:hud:move-by', delta),
    setWorkspaceTransfer: transferring => ipcRenderer.send('nara:hud:workspace-transfer', transferring),
    setBounds: bounds => ipcRenderer.send('nara:hud:set-bounds', bounds),
    resetLayout: () => ipcRenderer.invoke('nara:hud:reset-layout'),
    // Whether the band covers the window below the bar. Main pairs it with the
    // user's translucency setting to decide the native frost (macOS vibrancy /
    // Windows 11 DWM backdrop) — see hudFrostFor.
    setFrost: showing => ipcRenderer.invoke('nara:hud:frost', showing),
    // The HUD tells main which session it is on; main hands that back to the
    // app window when the HUD closes, so the app can re-home onto it.
    setSession: sessionId => ipcRenderer.send('nara:hud:session', sessionId),
    onGoto: callback => {
      const listener = (_event, sessionId) => callback(sessionId)
      ipcRenderer.on('nara:hud:goto', listener)

      return () => ipcRenderer.removeListener('nara:hud:goto', listener)
    },
    onChanged: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('nara:hud:changed', listener)

      return () => ipcRenderer.removeListener('nara:hud:changed', listener)
    },
    // Linux only, and silent elsewhere: where the cursor is, in page
    // coordinates, or null when it has left the window. Stands in for the
    // mousemove that `setIgnoreMouseEvents(true, { forward: true })` delivers on
    // macOS and Windows but not here.
    onCursor: callback => {
      const listener = (_event, point) => callback(point)
      ipcRenderer.on('nara:hud:cursor', listener)

      return () => ipcRenderer.removeListener('nara:hud:cursor', listener)
    },
    // Main's game-overlay watch: whether a fullscreen app (a game) is under
    // the HUD, so the renderer can step back to the low-opacity overlay
    // treatment while one owns the screen.
    onGameOverlay: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('nara:hud:game-overlay', listener)

      return () => ipcRenderer.removeListener('nara:hud:game-overlay', listener)
    }
  },
  hudModifier: {
    getSettings: () => ipcRenderer.invoke('nara:hud-modifier:settings:get'),
    setEnabled: enabled => ipcRenderer.invoke('nara:hud-modifier:settings:set', enabled),
    openPermissionSettings: () => ipcRenderer.invoke('nara:hud-modifier:permission'),
    onStatus: callback => {
      const listener = (_event: Electron.IpcRendererEvent, status: HudModifierStatus) => callback(status)
      ipcRenderer.on('nara:hud-modifier:status', listener)

      return () => ipcRenderer.removeListener('nara:hud-modifier:status', listener)
    }
  } satisfies HudModifierApi,
  // macOS native screenshot gesture; captures require a main-issued request.
  screenshot:
    process.platform === 'darwin'
      ? {
          getSettings: () => ipcRenderer.invoke('nara:screenshot:settings:get'),
          setEnabled: enabled => ipcRenderer.invoke('nara:screenshot:settings:set', enabled),
          openPermissionSettings: kind => ipcRenderer.invoke('nara:screenshot:permission', kind),
          capture: requestId => ipcRenderer.invoke('nara:screenshot:capture', requestId),
          onStatus: callback => {
            const listener = (_event, status) => callback(status)
            ipcRenderer.on('nara:screenshot:status', listener)

            return () => ipcRenderer.removeListener('nara:screenshot:status', listener)
          },
          onRequest: callback => {
            const channel = 'nara:screenshot:request'
            const listener = (_event, requestId) => callback(requestId)

            if (ipcRenderer.listenerCount(channel) === 0) {
              ipcRenderer.send('nara:screenshot:subscribe', true)
            }

            ipcRenderer.on(channel, listener)

            return () => {
              ipcRenderer.removeListener(channel, listener)

              if (ipcRenderer.listenerCount(channel) === 0) {
                ipcRenderer.send('nara:screenshot:subscribe', false)
              }
            }
          }
        }
      : undefined,
  // Quick Entry: the global-hotkey mini composer window. Main owns the OS
  // shortcut + the persisted preference; the quick window only captures text
  // and hands it back, and the primary renderer submits it through the normal
  // prompt path.
  quickEntry: {
    getSettings: () => ipcRenderer.invoke('nara:quick-entry:settings:get'),
    setSettings: patch => ipcRenderer.invoke('nara:quick-entry:settings:set', patch),
    // Invoke returns the delivery result so the draft is not lost (#85590).
    submit: payload => ipcRenderer.invoke('nara:quick-entry:submit', payload),
    // Main cannot invoke the primary renderer, so it receives this ack (#85590).
    ackSubmit: (correlationId, result) => ipcRenderer.send('nara:quick-entry:ack', { correlationId, result }),
    dismiss: () => ipcRenderer.send('nara:quick-entry:dismiss'),
    // Primary renderer → main → quick window: gateway connection state + the
    // recent-session options the target picker offers. Main caches the latest
    // payload so a freshly spawned quick window starts from truth.
    pushState: payload => ipcRenderer.send('nara:quick-entry:state', payload),
    // Quick window subscribes to those pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('nara:quick-entry:state', listener)

      return () => ipcRenderer.removeListener('nara:quick-entry:state', listener)
    },
    // Main → primary renderer: a submit captured by the quick window.
    onSubmit: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('nara:quick-entry:submit', listener)

      return () => ipcRenderer.removeListener('nara:quick-entry:submit', listener)
    },
    // Main → quick window: you were just summoned (reset draft + refocus).
    onShown: callback => {
      const listener = () => callback()
      ipcRenderer.on('nara:quick-entry:shown', listener)

      return () => ipcRenderer.removeListener('nara:quick-entry:shown', listener)
    },
    // Main → quick window: the outcome of a submit whose relay already timed
    // out. Delivery is now KNOWN — reconcile the unknown state instead of
    // leaving the user to resend a prompt that may already be delivered.
    onLateResult: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('nara:quick-entry:late-result', listener)

      return () => ipcRenderer.removeListener('nara:quick-entry:late-result', listener)
    }
  },
  getBootProgress: () => ipcRenderer.invoke('nara:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('nara:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('nara:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('nara:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('nara:connection-config:test', payload),
  // Opt-in OS-keychain encryption for stored gateway secrets (default off —
  // see secret-storage-policy.ts). get never touches the OS keychain.
  getSecretStorageEncryption: () => ipcRenderer.invoke('nara:secret-storage:get'),
  setSecretStorageEncryption: (on: boolean) => ipcRenderer.invoke('nara:secret-storage:set', on),
  // v2 multi-connection registry: named agent sources (local / remote / cloud / ssh).
  connections: {
    list: () => ipcRenderer.invoke('nara:connections:list'),
    save: payload => ipcRenderer.invoke('nara:connections:save', payload),
    remove: id => ipcRenderer.invoke('nara:connections:remove', id),
    setPrimary: id => ipcRenderer.invoke('nara:connections:set-primary', id),
    setLaunchMode: mode => ipcRenderer.invoke('nara:connections:set-launch-mode', mode),
    setLastUsed: id => ipcRenderer.invoke('nara:connections:set-last-used', id),
    test: id => ipcRenderer.invoke('nara:connections:test', id),
    updateManaged: id => ipcRenderer.invoke('nara:connections:update-managed', id),
    // Fan out `nara update` to every eligible registered connection.
    // Optional excludeIds skips rows the caller updates through another path.
    updateAll: options => ipcRenderer.invoke('nara:connections:update-all', options),
    // Registry lifecycle push (main → renderer): a connection was removed or
    // materially edited, so secondaries scoped to it must be disposed (and,
    // for edits, re-dialed at the new target).
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('nara:connections:changed', listener)

      return () => ipcRenderer.removeListener('nara:connections:changed', listener)
    }
  },
  sshConfigHosts: () => ipcRenderer.invoke('nara:ssh-config:hosts'),
  sshResolveHost: host => ipcRenderer.invoke('nara:ssh-config:resolve', host),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('nara:connection-config:probe', remoteUrl),
  // `options` lets a registry-editor draft sign in BEFORE it is saved: the
  // main process settles the draft's connection id up front so the login
  // window writes into the per-connection cookie jar the saved entry will
  // read (not the legacy shared jar an unsaved URL would fall back to).
  oauthLoginConnectionConfig: (remoteUrl, options) =>
    ipcRenderer.invoke('nara:connection-config:oauth-login', remoteUrl, options),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('nara:connection-config:oauth-logout', remoteUrl),
  // Nara Cloud: one portal login powers discovery + silent per-agent sign-in
  // (cloud-auto-discovery Phase 3).
  cloud: {
    status: () => ipcRenderer.invoke('nara:cloud:status'),
    login: () => ipcRenderer.invoke('nara:cloud:login'),
    logout: () => ipcRenderer.invoke('nara:cloud:logout'),
    discover: org => ipcRenderer.invoke('nara:cloud:discover', org),
    agentSignIn: dashboardUrl => ipcRenderer.invoke('nara:cloud:agent-sign-in', dashboardUrl)
  },
  profile: {
    getDefault: () => ipcRenderer.invoke('nara:profile:default:get'),
    setDefault: (route: DesktopProfileRoute) => ipcRenderer.invoke('nara:profile:default:set', route),
    onDefaultChanged: (callback: (route: DesktopProfileRoute | null) => void) => {
      const listener = (_event: Electron.IpcRendererEvent, route: DesktopProfileRoute | null) => callback(route)
      ipcRenderer.on('nara:profile:default:changed', listener)

      return () => ipcRenderer.removeListener('nara:profile:default:changed', listener)
    },
    get: () => ipcRenderer.invoke('nara:profile:get'),
    remember: name => ipcRenderer.invoke('nara:profile:remember', name),
    importConnections: (record: Record<string, string>) =>
      ipcRenderer.invoke('nara:profile:connections:import', record),
    rememberConnection: (connectionId: string, profile: string) =>
      ipcRenderer.invoke('nara:profile:connections:remember', connectionId, profile),
    set: name => ipcRenderer.invoke('nara:profile:set', name)
  },
  // The handler resolves an expected 404 with a sentinel instead of rejecting
  // (Electron logs a stack for every rejected invoke). Turn it back into the
  // rejection the renderer expects — see electron/api-expected-404.ts.
  api: request => ipcRenderer.invoke('nara:api', request).then(unwrapExpectedNotFound),
  notify: payload => ipcRenderer.invoke('nara:notify', payload),
  claimStartupLatency: () => ipcRenderer.invoke('nara:startup-latency:claim'),
  requestMicrophoneAccess: () => ipcRenderer.invoke('nara:requestMicrophoneAccess'),
  readWindowBelow: () => ipcRenderer.invoke('nara:window:readBelow'),
  readFileDataUrl: filePath => ipcRenderer.invoke('nara:readFileDataUrl', filePath),
  readFileDataUrlForAttach: filePath => ipcRenderer.invoke('nara:readFileDataUrlForAttach', filePath),
  dataUrlReadMax: {
    get: () => ipcRenderer.invoke('nara:data-url-read-max:get'),
    set: maxMb => ipcRenderer.invoke('nara:data-url-read-max:set', maxMb)
  },
  readFileText: filePath => ipcRenderer.invoke('nara:readFileText', filePath),
  readPluginSource: (filePath: string) => ipcRenderer.invoke('nara:readPluginSource', filePath),
  selectPaths: options => ipcRenderer.invoke('nara:selectPaths', options),
  selectSavePath: options => ipcRenderer.invoke('nara:selectSavePath', options),
  saveTextFileAs: request => ipcRenderer.invoke('nara:saveTextFileAs', request),
  writeClipboard: text => ipcRenderer.invoke('nara:writeClipboard', text),
  readClipboard: () => ipcRenderer.invoke('nara:readClipboard'),
  saveGatewayFile: payload => ipcRenderer.invoke('nara:saveGatewayFile', payload),
  saveImageFromUrl: url => ipcRenderer.invoke('nara:saveImageFromUrl', url),
  contextMenuEdit: command => ipcRenderer.invoke('nara:context-menu:edit', command),
  contextMenuCopyImage: () => ipcRenderer.invoke('nara:context-menu:copy-image'),
  contextMenuSpellcheck: action => ipcRenderer.invoke('nara:context-menu:spellcheck', action),
  contextMenuGuestAddWord: payload => ipcRenderer.invoke('nara:context-menu:guest-add-word', payload),
  spellcheckDictionary: (op, word) => ipcRenderer.invoke('nara:spellcheck:dictionary', { op, word }),
  onContextMenuSpellcheck: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nara:context-menu-spellcheck', listener)

    return () => ipcRenderer.removeListener('nara:context-menu-spellcheck', listener)
  },
  saveImageBuffer: (data, ext, name) => ipcRenderer.invoke('nara:saveImageBuffer', { data, ext, name }),
  capturePreview: payload => ipcRenderer.invoke('nara:capturePreview', payload),
  savePastedText: text => ipcRenderer.invoke('nara:savePastedText', { text }),
  saveClipboardImage: () => ipcRenderer.invoke('nara:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('nara:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('nara:watchPreviewFile', url),
  watchDirectory: dir => ipcRenderer.invoke('nara:watchDirectory', dir),
  stopPreviewFileWatch: id => ipcRenderer.invoke('nara:stopPreviewFileWatch', id),
  setActiveWork: payload => ipcRenderer.send('nara:active-work', payload),
  scheduleStreamWorkWake: (token, delayMs) => ipcRenderer.send('nara:stream-work-wake', { token, delayMs }),
  onStreamWorkWake: callback => {
    const listener = (_event, token) => callback(token)
    ipcRenderer.on('nara:stream-work-ready', listener)

    return () => ipcRenderer.removeListener('nara:stream-work-ready', listener)
  },
  setTitleBarTheme: payload => ipcRenderer.send('nara:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('nara:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('nara:translucency', payload),
  setKeepAwake: mode => ipcRenderer.send('nara:keep-awake', mode),
  // Once per computer, after a timed sleep interrupted a turn with keep-awake off.
  onKeepAwakeOffer: callback => {
    const listener = () => callback()
    ipcRenderer.on('nara:keep-awake-offer', listener)

    return () => ipcRenderer.removeListener('nara:keep-awake-offer', listener)
  },
  minimizeToTray: {
    get: () => ipcRenderer.invoke('nara:minimize-to-tray:get'),
    set: on => ipcRenderer.invoke('nara:minimize-to-tray:set', on),
    onChanged: callback => {
      const listener = (_event, status) => callback(status)
      ipcRenderer.on('nara:minimize-to-tray:changed', listener)

      return () => ipcRenderer.removeListener('nara:minimize-to-tray:changed', listener)
    }
  },
  setDisableF12: blocked => ipcRenderer.send('nara:devtools:disable-f12', blocked),
  setF12ShortcutActive: active => ipcRenderer.send('nara:f12ShortcutActive', Boolean(active)),
  onF12Shortcut: callback => {
    const listener = (_event, input) => callback(input)
    ipcRenderer.on('nara:f12-shortcut', listener)

    return () => ipcRenderer.removeListener('nara:f12-shortcut', listener)
  },
  setPreviewShortcutActive: active => ipcRenderer.send('nara:previewShortcutActive', Boolean(active)),
  setPreviewGuestHidden: (webContentsId, hidden) =>
    ipcRenderer.send('nara:preview-guest-hidden', { webContentsId, hidden: Boolean(hidden) }),
  beginPreviewGuestActivity: webContentsId => ipcRenderer.invoke('nara:preview-guest-activity:begin', webContentsId),
  endPreviewGuestActivity: token => ipcRenderer.invoke('nara:preview-guest-activity:end', token),
  executePreviewGuestScript: (token, code) => ipcRenderer.invoke('nara:preview-guest-activity:script', token, code),
  syncPreviewSignins: request => ipcRenderer.invoke('nara:preview-signins:sync', request),
  migratePreviewSigninsForProfile: (request: { oldProfile: string; newProfile: string }) =>
    ipcRenderer.invoke('nara:preview-signins:profile-renamed', request),
  dropPreviewSigninsForProfile: (request: { profile: string }) =>
    ipcRenderer.invoke('nara:preview-signins:profile-deleted', request),
  openExternal: url => ipcRenderer.invoke('nara:openExternal', url),
  freeTierChallenge: {
    // Load the account service's challenge page in a hidden window (revealed
    // only if the page asks for the human). Resolves with how it ended.
    run: request => ipcRenderer.invoke('nara:freeTierChallenge:run', request)
  },
  mcpOauth: {
    // One-shot loopback listener for MCP OAuth against remote backends: bind
    // on this machine, hand redirectUri to mcp.servers.oauth.start, then wait
    // for the provider redirect and relay code/state via oauth.callback.
    listen: () => ipcRenderer.invoke('nara:mcp-oauth:listen'),
    wait: (id, timeoutMs) => ipcRenderer.invoke('nara:mcp-oauth:wait', id, timeoutMs),
    cancel: id => ipcRenderer.invoke('nara:mcp-oauth:cancel', id)
  },
  openPreviewInBrowser: url => ipcRenderer.invoke('nara:openPreviewInBrowser', url),
  reachPreviewUrl: url => ipcRenderer.invoke('nara:preview:reach', url),
  setActiveConnectionRoute: route => ipcRenderer.send('nara:connection:active-route', route),
  fetchLinkTitle: url => ipcRenderer.invoke('nara:fetchLinkTitle', url),
  resolveFavicon: url => ipcRenderer.invoke('nara:resolveFavicon', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('nara:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('nara:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('nara:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('nara:setting:defaultProjectDir:pick')
  },
  preparedSubmissions: {
    read: () => ipcRenderer.invoke('nara:prepared-submissions:read'),
    update: (key, entry) => ipcRenderer.invoke('nara:prepared-submissions:update', key, entry),
    compareAndSet: (key, expected, entry) =>
      ipcRenderer.invoke('nara:prepared-submissions:compare-and-set', key, expected, entry)
  },
  zoom: {
    // Current zoom of this window, as { level, percent }.
    get: () => ipcRenderer.invoke('nara:zoom:get'),
    // Synchronous zoom factor (1 = 100%). Coordinate math needs it in the
    // same tick as the event it converts, so no IPC round-trip here.
    factor: () => webFrame.getZoomFactor(),
    setPercent: percent => ipcRenderer.send('nara:zoom:set-percent', percent),
    // Fires on every zoom change, including the Ctrl/Cmd +/-/0 shortcuts,
    // so the settings UI can stay in sync with the keyboard.
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('nara:zoom:changed', listener)

      return () => ipcRenderer.removeListener('nara:zoom:changed', listener)
    }
  },
  revealLogs: () => ipcRenderer.invoke('nara:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('nara:logs:recent'),
  // Fire-and-forget: persists a renderer error-boundary catch (with component
  // stack) to desktop.log so crashes survive the window (#79428).
  reportRendererError: report => ipcRenderer.send('nara:logs:renderer-error', report),
  logLine: (line: string): void => ipcRenderer.send('nara:logs:renderer-line', line),
  readDir: dirPath => ipcRenderer.invoke('nara:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('nara:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('nara:fs:reveal', targetPath),
  openDir: dirPath => ipcRenderer.invoke('nara:fs:openDir', dirPath),
  desktopPluginsRoot: () => ipcRenderer.invoke('nara:fs:desktopPluginsRoot'),
  reconcileDesktopPlugins: async () => (await ipcRenderer.invoke('nara:fs:reconcileDesktopPlugins')).published,
  reconcileDesktopPluginsReport: () => ipcRenderer.invoke('nara:fs:reconcileDesktopPlugins'),
  logsRoot: (profile?: string) => ipcRenderer.invoke('nara:fs:logsRoot', profile),
  renamePath: (targetPath, newName) => ipcRenderer.invoke('nara:fs:rename', targetPath, newName),
  writeTextFile: (filePath, content) => ipcRenderer.invoke('nara:fs:writeText', filePath, content),
  trashPath: targetPath => ipcRenderer.invoke('nara:fs:trash', targetPath),
  pluginFiles: {
    request: (pluginId, labels) => ipcRenderer.invoke('nara:pluginFiles:request', pluginId, labels),
    grants: pluginId => ipcRenderer.invoke('nara:pluginFiles:grants', pluginId),
    revoke: (pluginId, folderId) => ipcRenderer.invoke('nara:pluginFiles:revoke', pluginId, folderId),
    op: (pluginId, request) => ipcRenderer.invoke('nara:pluginFiles:op', pluginId, request),
    onChanged: callback => {
      const listener = (_event, change) => callback(change)
      ipcRenderer.on('nara:pluginFiles:changed', listener)

      return () => ipcRenderer.removeListener('nara:pluginFiles:changed', listener)
    }
  },
  git: {
    worktreeList: repoPath => ipcRenderer.invoke('nara:git:worktreeList', repoPath),
    worktreeAdd: (repoPath, options) => ipcRenderer.invoke('nara:git:worktreeAdd', repoPath, options),
    worktreeRemove: (repoPath, worktreePath, options) =>
      ipcRenderer.invoke('nara:git:worktreeRemove', repoPath, worktreePath, options),
    branchSwitch: (repoPath, branch) => ipcRenderer.invoke('nara:git:branchSwitch', repoPath, branch),
    branchList: repoPath => ipcRenderer.invoke('nara:git:branchList', repoPath),
    baseBranchList: repoPath => ipcRenderer.invoke('nara:git:baseBranchList', repoPath),
    repoStatus: repoPath => ipcRenderer.invoke('nara:git:repoStatus', repoPath),
    fileDiff: (repoPath, filePath) => ipcRenderer.invoke('nara:git:fileDiff', repoPath, filePath),
    scanRepos: (roots, options) => ipcRenderer.invoke('nara:git:scanRepos', roots, options),
    review: {
      list: (repoPath, scope, baseRef) => ipcRenderer.invoke('nara:git:review:list', repoPath, scope, baseRef),
      diff: (repoPath, filePath, scope, baseRef, staged) =>
        ipcRenderer.invoke('nara:git:review:diff', repoPath, filePath, scope, baseRef, staged),
      stage: (repoPath, filePath) => ipcRenderer.invoke('nara:git:review:stage', repoPath, filePath),
      unstage: (repoPath, filePath) => ipcRenderer.invoke('nara:git:review:unstage', repoPath, filePath),
      revert: (repoPath, filePath) => ipcRenderer.invoke('nara:git:review:revert', repoPath, filePath),
      revParse: (repoPath, ref) => ipcRenderer.invoke('nara:git:review:revParse', repoPath, ref),
      commit: (repoPath, message, push) => ipcRenderer.invoke('nara:git:review:commit', repoPath, message, push),
      commitContext: repoPath => ipcRenderer.invoke('nara:git:review:commitContext', repoPath),
      push: repoPath => ipcRenderer.invoke('nara:git:review:push', repoPath),
      shipInfo: repoPath => ipcRenderer.invoke('nara:git:review:shipInfo', repoPath),
      prList: (repoPath, branches, numbers) =>
        ipcRenderer.invoke('nara:git:review:prList', repoPath, branches, numbers),
      createPr: repoPath => ipcRenderer.invoke('nara:git:review:createPr', repoPath)
    }
  },
  terminal: {
    attach: id => ipcRenderer.invoke('nara:terminal:attach', id),
    cwd: id => ipcRenderer.invoke('nara:terminal:cwd', id),
    dispose: id => ipcRenderer.invoke('nara:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('nara:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('nara:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('nara:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `nara:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `nara:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('nara:close-preview-requested', listener)

    return () => ipcRenderer.removeListener('nara:close-preview-requested', listener)
  },
  onPreviewNav: callback => {
    const listener = (_event, command) => callback(command)
    ipcRenderer.on('nara:preview-nav', listener)

    return () => ipcRenderer.removeListener('nara:preview-nav', listener)
  },
  onOpenFolderRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('nara:open-folder-requested', listener)

    return () => ipcRenderer.removeListener('nara:open-folder-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('nara:open-updates', listener)

    return () => ipcRenderer.removeListener('nara:open-updates', listener)
  },
  onDeepLink: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nara:deep-link', listener)

    return () => ipcRenderer.removeListener('nara:deep-link', listener)
  },
  signalDeepLinkReady: () => ipcRenderer.invoke('nara:deep-link-ready'),
  probePluginRepo: payload => ipcRenderer.invoke('nara:plugin:probe', payload),
  installDesktopPlugin: payload => ipcRenderer.invoke('nara:plugin:installDesktop', payload),
  removeDesktopPlugin: payload => ipcRenderer.invoke('nara:plugin:removeDesktop', payload),
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nara:window-state-changed', listener)

    return () => ipcRenderer.removeListener('nara:window-state-changed', listener)
  },
  onFocusSession: callback => {
    const listener = (_event, sessionId) => callback(sessionId)
    ipcRenderer.on('nara:focus-session', listener)

    return () => ipcRenderer.removeListener('nara:focus-session', listener)
  },
  onNotificationAction: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nara:notification-action', listener)

    return () => ipcRenderer.removeListener('nara:notification-action', listener)
  },
  onNotificationActivate: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nara:notification-activate', listener)

    return () => ipcRenderer.removeListener('nara:notification-activate', listener)
  },
  onExternalOpenFailed: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nara:external-open-failed', listener)

    return () => ipcRenderer.removeListener('nara:external-open-failed', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nara:preview-file-changed', listener)

    return () => ipcRenderer.removeListener('nara:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nara:backend-exit', listener)

    return () => ipcRenderer.removeListener('nara:backend-exit', listener)
  },
  // Soft gateway-mode apply finished tearing down the primary backend. Renderer
  // should wipe session lists + re-dial without a window reload.
  onConnectionApplied: callback => {
    const listener = () => callback()
    ipcRenderer.on('nara:connection:applied', listener)

    return () => ipcRenderer.removeListener('nara:connection:applied', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('nara:power-resume', listener)

    return () => ipcRenderer.removeListener('nara:power-resume', listener)
  },
  // AC ↔ battery transitions; renderers slow their backstop polls on battery.
  getOnBattery: () => ipcRenderer.invoke('nara:power-battery:get'),
  onBatteryChanged: callback => {
    const listener = (_event, onBattery) => callback(Boolean(onBattery))
    ipcRenderer.on('nara:power-battery', listener)

    return () => ipcRenderer.removeListener('nara:power-battery', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nara:boot-progress', listener)

    return () => ipcRenderer.removeListener('nara:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.ts (apps/desktop/electron/bootstrap-runner.ts).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('nara:bootstrap:get'),
  probeLocalBackend: () => ipcRenderer.invoke('nara:local-backend:probe'),
  continueBootstrapLocal: () => ipcRenderer.invoke('nara:bootstrap:continue-local'),
  recycleBackend: profile => ipcRenderer.invoke('nara:backend:recycle', profile),
  resetBootstrap: () => ipcRenderer.invoke('nara:bootstrap:reset'),
  updateHold: {
    recheck: () => ipcRenderer.invoke('nara:update-hold:recheck'),
    quit: () => ipcRenderer.invoke('nara:update-hold:quit'),
    startAnyway: (request: { holdId: string; confirmed: true }) =>
      ipcRenderer.invoke('nara:update-hold:start-anyway', request)
  },
  repairBootstrap: () => ipcRenderer.invoke('nara:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('nara:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('nara:bootstrap:event', listener)

    return () => ipcRenderer.removeListener('nara:bootstrap:event', listener)
  },
  getVersion: (scope?: { connectionId?: string; profile?: string }) => ipcRenderer.invoke('nara:version', scope),
  relaunchApp: () => ipcRenderer.invoke('nara:app:relaunch'),
  getMachineProfile: () => ipcRenderer.invoke('nara:machine:profile'),
  getRemoteDisplayReason: () => ipcRenderer.invoke('nara:get-remote-display-reason'),
  uninstall: {
    summary: () => ipcRenderer.invoke('nara:uninstall:summary'),
    run: mode => ipcRenderer.invoke('nara:uninstall:run', { mode }),
    openAppsSettings: () => ipcRenderer.invoke('nara:uninstall:openAppsSettings')
  },
  updates: {
    check: opts => ipcRenderer.invoke('nara:updates:check', opts),
    apply: opts => ipcRenderer.invoke('nara:updates:apply', opts),
    setChannel: name => ipcRenderer.invoke('nara:updates:channel:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('nara:updates:progress', listener)

      return () => ipcRenderer.removeListener('nara:updates:progress', listener)
    },
    takePendingRun: () => ipcRenderer.invoke('nara:updates:metric:take'),
    ackPendingRun: sent => ipcRenderer.invoke('nara:updates:metric:ack', sent),
    onPendingRun: callback => {
      const listener = () => callback()
      ipcRenderer.on('nara:updates:metric:pending', listener)

      return () => ipcRenderer.removeListener('nara:updates:metric:pending', listener)
    }
  },
  desktopMetrics: {
    setEnabled: (on, profile) => ipcRenderer.invoke('nara:desktop-metrics:set-enabled', on, profile),
    takeRendererCrashes: () => ipcRenderer.invoke('nara:desktop-metrics:crash:take'),
    ackRendererCrashes: sent => ipcRenderer.invoke('nara:desktop-metrics:crash:ack', sent)
  },
  themes: {
    fetchMarketplace: id => ipcRenderer.invoke('nara:vscode-theme:fetch', id),
    searchMarketplace: query => ipcRenderer.invoke('nara:vscode-theme:search', query)
  },
  // Find-in-page (Ctrl/Cmd+F): delegates to Electron's
  // webContents.findInPage on the IPC sender's window so a Cmd+F pressed
  // in a secondary session window searches THAT window, not the primary.
  // `onFoundInPage` returns the unsubscribe fn; the renderer wires it via
  // `initFindInPageListener` in store/find-in-page.ts and tears it down
  // when the FindBar unmounts.
  findInPage: (query, options) => ipcRenderer.invoke('nara:find-in-page', query, options),
  stopFindInPage: () => ipcRenderer.invoke('nara:stop-find-in-page'),
  onFoundInPage: callback => {
    const listener = (_event, result) => callback(result)
    ipcRenderer.on('nara:found-in-page', listener)

    return () => ipcRenderer.removeListener('nara:found-in-page', listener)
  },
  // Main-process `before-input-event` forwards Ctrl/Cmd+F here so renderer
  // can open the FindBar even when the GTK compositor has already grabbed
  // the chord at the windowing layer (#81727).
  onOpenFindBarRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('nara:open-find-bar', listener)

    return () => ipcRenderer.removeListener('nara:open-find-bar', listener)
  }
})
