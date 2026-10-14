# Changelog

## 1.5.0 — 2026-10-14

### Added
- **Fixed look**: Fusion style, complete cosmic palette (disabled states included) and
  embedded Source Sans 3 font (`assets/polices`, OFL) — the interface no longer depends on
  the system's light/dark theme or fonts (`gui/theme.py`, shared `interface_kit.py`).
- **Full file browser** on Linux for every Open / Save / Choose-folder dialog: Qt's complete
  dialog with the usual places in the sidebar, instead of the reduced desktop-portal one;
  Windows and macOS keep their own (complete) dialogs.
- **PDF manual** in French and English, house format, real screenshots, opened by
  *Help > User manual (PDF)* (Shift+F1); sources in `docs/src/`, screenshots by
  `docs/captures.py`, build by `docs/src/compiler.py`. It replaces `USER_MANUAL_*.pdf`, whose
  installation, update and bug-report chapters described the former mechanisms.
- **Icon**: one vector source, `assets/icon.svg`, rendered by `assets/make_logo.py` to PNG
  16–1024, `.ico` (Windows) and `.icns` (macOS); also on the manual's cover and in *About*.
- Tests: real start-up of the program, fixed style, manuals present.

## 1.4.0 — 2026-10-14

### Added
- **macOS and Linux packages**, built by the same single workflow as the Windows installer
  (`release.yml`, triggered by a `vX.Y.Z` tag): `.dmg` for Apple Silicon and Intel, `.tar.gz`
  for Linux x86_64 and ARM64 with `installer.sh` (user install, menu entry, no sudo), plus the
  permanent link `releases/latest/download/AstroManager-Setup.exe`.
- **Automatic update on all three systems** through the shared kit (`updater.py`): it downloads
  the application archive `astromanager-app-X.Y.Z.zip`, refuses any address outside GitHub,
  restores executable bits, and shows the release notes in the interface language.
- Problem reports (`reporting.py`): consent asked at first launch, *Help > Report a problem…*
  and *Help > Send problem reports automatically*; crashes, native crashes and interface
  freezes are reported (freeze watchdog). Reports stay outside the installation folder.
- `--check`: checks that the application and its dependencies load, then exits (used by the
  package build on every system).
- Tests: no hard-coded interface text (`tests/test_i18n_textes.py`), interface under Xvfb
  (`tests/test_gui.py`), both run by CI.
- Observatory instruments of the Observatoire de Haute-Provence used by the DU ECU of the Observatoire de
  Paris, recognised automatically from FITS and XISF headers (`database/observatories.py`):
  - T120 (1 200 mm Newtonian, measured focal length 7 232 mm, f/6) with the Andor iKon-L 936
    (13.5 µm; 2×2 binning → 0.770″/px, 1×1 → 0.385″/px) and the Andor Marana 4.2B-11 sCMOS
    (11 µm; 2×2 binning → 0.627″/px);
  - IRIS (500 mm, ~4 072 mm, f/8.1) with FLI ProLine 2048 (13.5 µm, 0.684″/px) and ProLine 4096
    (9 µm, 0.456″/px).
  Keywords used: `TELESCOP` ('OHP T120', 'IRIS OHP', 'ACP->NTM' with `OBSERVAT` = 'IRiS'), `INSTRUME`
  ('Andor Tech', 'Andor sCMOS (SDK3)', FLI serial numbers or 'FLI'), `APTDIA`, `FOCALLEN`, `XPIXSZ`,
  `XBINNING`, `NAXIS1`. Tests on real, anonymised headers (`tests/test_observatoires_ohp.py`).

### Changed
- The Windows installer now deletes the previous version before copying the new one, and
  detects a running AstroManager (named mutex `AstroManagerEnCours`).
- Releases are published only by `release.yml` on a version tag; the automatic patch bump on
  every push to `main` (`auto-release.yml`) is gone, as is the source-zipball updater with its
  `SHA256SUMS` asset.
- On Windows, a French system (locale `French_France`) now starts the interface in French.
- The remaining hard-coded texts (PixInsight import, disk space, target tracking, status bar,
  calendar) are translated.
- Removal of personal mentions; installer publisher, header of `reporting.py` and author line now read
  ARP273-ROSE. Privacy guard `tests/test_confidentialite.py` (files, PDF text, PNG, binaries), run by CI.
- The Andor iKon-L 936 entry now uses datasheet values (read noise 2.9 e-, QE 0.9).

### Removed
- PyInstaller build (`astromanager.spec`, `build.bat`, `build.sh`), the former in-app update
  dialog and the former bug reporter (its endpoint did not exist; it wrote into the program
  folder).
