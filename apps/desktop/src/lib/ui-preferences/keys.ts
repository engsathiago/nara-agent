/**
 * Which persisted keys are machine-level UI preferences (#145213).
 *
 * Only these leave localStorage for the machine's shared store, so native
 * Desktop and every browser that opens this machine's Webapp show the same
 * choices. Scoped families keep their scope inside the key name (a
 * `….profile.<name>` or per-connection suffix): only the location changes.
 *
 * Deliberately NOT here (they stay in this browser/window):
 * - credentials, grants and connection config: gateway registry, custom model
 *   endpoints, plugin decisions and preview-script grants, embed permissions;
 * - per-window or per-device runtime state: layout tree, open tiles and tabs,
 *   last route/session, scroll, zoom, pet and popout geometry, keep-awake;
 * - drafts, queues, journals and caches: composer queue, in-flight turns,
 *   pending/prepared submissions, previews, pricing, backend skin cache, the
 *   "provider configured" onboarding cache (each backend answers that itself);
 * - one-off notices: butterbar, update and real-profile prompts.
 */

const SHARED_KEYS: ReadonlySet<string> = new Set([
  // Appearance.
  'nara-desktop-theme-v2',
  'nara-desktop-mode-v1',
  'nara-desktop-profile-themes-v1',
  'nara-desktop-profile-modes-v1',
  'nara-desktop-user-themes-v1',
  'nara.desktop.backdrop.v1',
  'nara.desktop.chat-text-scale.v1',
  'nara.desktop.interfaceMode.v1',
  'nara.desktop.textDirection',
  'nara.desktop.translucency.v2',
  'nara.desktop.user-bubble-transparency.v1',
  // Sessions sidebar and profile rail.
  'nara.desktop.agentsGroupedByWorkspace',
  'nara.desktop.profileColors',
  'nara.desktop.profileOrder',
  'nara.desktop.profileRailVisible',
  'nara.desktop.sessionListDensity',
  'nara.desktop.sessionOrder',
  'nara.desktop.sessionOrder.manual',
  'nara.desktop.showAllProfiles',
  'nara.desktop.sidebarAgentsGrouped.allProfiles',
  'nara.desktop.sidebarCardRows',
  'nara.desktop.sidebarGrouping',
  'nara.desktop.sidebarGrouping.allProfiles',
  'nara.desktop.sidebarRowMeta',
  'nara.desktop.sidebarShowAllSessions',
  'nara.desktop.sidebarShowArchived',
  'nara.desktop.sidebarSortKey',
  // Status bar.
  'nara.desktop.statusbarHidden.v2',
  'nara.desktop.statusbarVisible.v2',
  // Transcript and tools.
  'nara.desktop.hideThreadTimeline',
  'nara.desktop.reasoning.collapsedByDefault',
  'nara.desktop.toolView.hideCodeDiffs',
  'nara.desktop.toolView.technical',
  // Shell, panes and behaviour.
  'nara.desktop.alwaysExternalLinks.v1',
  'nara.desktop.capabilities.catalogCardView',
  'nara.desktop.composerPopout.enabled',
  'nara.desktop.composerPopout.gesturesEnabled',
  'nara.desktop.files.showIgnored',
  'nara.desktop.keybinds',
  'nara.desktop.layoutPresets.v2',
  'nara.desktop.panesFlipped',
  'nara.desktop.tabStripDefault',
  'nara.desktop.titlebarAppActions',
  // Guidance: what the user already skipped, saw or dismissed does not come
  // back in every new browser or origin (#145600).
  'nara-onboarding-skipped-v1',
  'nara.desktop.tips.last.v1',
  'nara.desktop.tips.next.v1',
  'nara.desktop.tips.retired.v1',
  'nara.desktop.tips.rotation.v1',
  'nara.desktop.tips.shownAt.v1',
  'nara.desktop.tours.v1',
  // Sound and media.
  'nara.desktop.autoSpeakReplies',
  'nara.desktop.completionSoundVariantId',
  'nara.desktop.hapticsMuted',
  'nara.desktop.videoPlaybackSpeed',
  // Model picker.
  'nara.desktop.collapsed-providers',
  'nara.desktop.favorite-models',
  // visible-models is a diff against known-models: they only make sense together.
  'nara.desktop.known-models',
  'nara.desktop.model-presets',
  'nara.desktop.visible-models'
])

/** Families whose scope rides in the key suffix (gateway aliases/order/collapsed). */
const SHARED_PREFIXES: readonly string[] = ['nara.desktop.sidebar.gatewayGroups.v1.']

export function isSharedPreferenceKey(key: string): boolean {
  return SHARED_KEYS.has(key) || SHARED_PREFIXES.some(prefix => key.startsWith(prefix))
}
