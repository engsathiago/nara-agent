# Self-contained Nara TUI, compiled by the same recipe as pnpm.
{ naraNpmLib, ... }:
naraNpmLib.buildPnpmPackage {
  dirs = [
    "ui-tui"
    "apps/shared"
    "scripts/build/tui.mjs"
    "scripts/build/freshness.mjs"
    "scripts/build/frontend-common.mjs"
  ];

  doCheck = false;

  buildPhase = ''
    runHook preBuild
    node scripts/build/tui.mjs --source "$PWD" --out "$TMPDIR/tui-product"
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p $out/lib/nara-tui
    cp -r "$TMPDIR/tui-product/." $out/lib/nara-tui/
    runHook postInstall
  '';
}
