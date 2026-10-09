# Changelog

## Unreleased — 2026-10-09

### Added
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
- `[no release]` in a commit message skips the automatic release.

### Changed
- Removal of personal mentions; installer publisher, header of `reporting.py` and author line now read
  ARP273-ROSE. Privacy guard `tests/test_confidentialite.py` (files, PDF text, PNG, binaries), run by CI.
- The Andor iKon-L 936 entry now uses datasheet values (read noise 2.9 e-, QE 0.9).
