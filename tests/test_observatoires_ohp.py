"""Instruments de l'Observatoire de Haute-Provence (T120, IRIS) : base et détection par en-têtes.

Les en-têtes ci-dessous sont des extraits RÉELS, anonymisés (observateur, coordonnées, dates et noms de cible
retirés), d'images du DU ECU de l'Observatoire de Paris converties en XISF : seules les clés qui servent à
reconnaître l'instrument sont gardées, avec leur écriture d'origine (chaînes FITS entre apostrophes, « -> »
échappé en XML dans un fichier XISF).
"""
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from database.observatories import (  # noqa: E402
    OBSERVATORY_CAMERAS, OBSERVATORY_TELESCOPES, detect_observatory_equipment,
)

# (en-tête, télescope, caméra, binning, échelle ″/px attendue)
ENTETES_REELS = {
    'T120 iKon-L bin 2 (2025)': ({
        'TELESCOP': "'OHP T120'", 'INSTRUME': "'Andor Tech'", 'APTDIA': '1200.0000000000000',
        'FOCALLEN': '7200.0000000000000', 'XPIXSZ': '27.000000000000000', 'XBINNING': '2', 'NAXIS1': '1024',
        'SWCREATE': "'MaxIm DL Version 6.50 260320 2AFRX'"},
        'OHP T120', 'Andor iKon-L 936', 2, 0.770),
    'T120 iKon-L bin 1 (2016)': ({
        'TELESCOP': "'OHP T120'", 'INSTRUME': "'Andor Tech'", 'APTDIA': '1200.0000000000000',
        'FOCALLEN': '7200.0000000000000', 'XPIXSZ': '13.500000000000000', 'XBINNING': '1', 'NAXIS1': '2048'},
        'OHP T120', 'Andor iKon-L 936', 1, 0.385),
    'T120 Marana bin 2 (2026)': ({
        'TELESCOP': "'OHP T120'", 'INSTRUME': "'Andor sCMOS (SDK3)'", 'APTDIA': '1200.0000000000000',
        'FOCALLEN': '7200.0000000000000', 'XPIXSZ': '21.911', 'XBINNING': '2', 'NAXIS1': '1024',
        'READOUTM': "'100MHz'"},
        'OHP T120', 'Andor Marana 4.2B-11', 2, 0.627),
    'T120 Marana sans XPIXSZ': ({
        'TELESCOP': 'OHP T120', 'INSTRUME': 'Andor sCMOS (SDK3)', 'XBINNING': 2, 'NAXIS1': 1024},
        'OHP T120', 'Andor Marana 4.2B-11', 2, 0.627),
    'IRIS ProLine 2048, TELESCOP « IRIS OHP »': ({
        'TELESCOP': "'IRIS OHP'", 'INSTRUME': "'flipro0:PL0394113'", 'OBSERVAT': "'IRiS'", 'APTDIA': '500.00000000000000',
        'FOCALLEN': '4072.7', 'XPIXSZ': '13.500000000000000', 'XBINNING': '1', 'NAXIS1': '2048', 'EGAIN': '1.5000000000000000'},
        'OHP IRIS', 'FLI ProLine 2048', 1, 0.684),
    'IRIS ProLine 2048, TELESCOP « ACP->NTM » (XML échappé)': ({
        'TELESCOP': "'ACP-&gt;NTM'", 'INSTRUME': "'flipro0:PL0394113'", 'OBSERVAT': "'IRiS'", 'APTDIA': '500.00000000000000',
        'FOCALLEN': '4072.7', 'XPIXSZ': '13.500000000000000', 'XBINNING': '1', 'NAXIS1': '2048'},
        'OHP IRIS', 'FLI ProLine 2048', 1, 0.684),
    'IRIS ProLine 4096, INSTRUME « FLI »': ({
        'TELESCOP': "'IRIS OHP'", 'INSTRUME': "'FLI'", 'OBSERVAT': "'IRiS'", 'APTDIA': '500.00000000000000',
        'FOCALLEN': '4070.1', 'XPIXSZ': '9.0000000000000000', 'XBINNING': '1', 'NAXIS1': '4096', 'READOUTM': "'8 MHz'"},
        'OHP IRIS', 'FLI ProLine 4096', 1, 0.456),
    'IRIS ProLine 4096, ACP->NTM + numéro de série': ({
        'TELESCOP': 'ACP->NTM', 'INSTRUME': 'flipro0:PL1344016', 'OBSERVAT': 'IRiS', 'XPIXSZ': 9.0, 'XBINNING': 1,
        'NAXIS1': 4096},
        'OHP IRIS', 'FLI ProLine 4096', 1, 0.456),
}


@pytest.mark.parametrize('nom', list(ENTETES_REELS))
def test_detection_sur_en_tetes_reels(nom):
    entete, telescope, camera, binning, echelle = ENTETES_REELS[nom]
    r = detect_observatory_equipment(entete)
    assert r is not None, nom
    assert (r['telescope'], r['camera'], r['binning']) == (telescope, camera, binning)
    assert r['image_scale_arcsec'] == pytest.approx(echelle, abs=0.0015)


def test_acp_ntm_seul_n_est_pas_iris():
    """« ACP->NTM » est la chaîne générique du logiciel ACP : sans OBSERVAT 'IRiS' ni optique d'IRIS, rien."""
    assert detect_observatory_equipment({'TELESCOP': 'ACP->NTM', 'INSTRUME': 'FLI', 'XPIXSZ': 9.0}) is None
    # … mais l'ouverture et la focale d'IRIS suffisent quand TELESCOP est technique
    r = detect_observatory_equipment({'TELESCOP': 'ACP->NTM', 'APTDIA': 500.0, 'FOCALLEN': 4071.0,
                                      'INSTRUME': 'FLI', 'XPIXSZ': 13.5, 'XBINNING': 1})
    assert r['telescope'] == 'OHP IRIS' and r['camera'] == 'FLI ProLine 2048'


def test_materiel_amateur_non_reconnu():
    for h in ({'TELESCOP': 'Takahashi FSQ-106', 'INSTRUME': 'ZWO ASI6200MM Pro', 'FOCALLEN': 530, 'XPIXSZ': 3.76},
              {'TELESCOP': 'Andor Tech', 'INSTRUME': 'Andor Tech'}, {'INSTRUME': 'FLI'}, {}, None):
        assert detect_observatory_equipment(h) is None


def test_valeurs_de_la_base():
    t120, iris = OBSERVATORY_TELESCOPES['OHP T120'], OBSERVATORY_TELESCOPES['OHP IRIS']
    assert (t120['diameter_mm'], t120['focal_length_mm']) == (1200.0, 7232.0)
    assert t120['f_number'] == pytest.approx(7232 / 1200, abs=0.01)
    assert (iris['diameter_mm'], iris['focal_length_mm']) == (500.0, 4072.0)
    assert iris['f_number'] == pytest.approx(4072 / 500, abs=0.01)
    px = {k: (v['pixel_size'], v['width_px']) for k, v in OBSERVATORY_CAMERAS.items()}
    assert px == {'Andor iKon-L 936': (13.5, 2048), 'Andor Marana 4.2B-11': (11.0, 2048),
                  'FLI ProLine 2048': (13.5, 2048), 'FLI ProLine 4096': (9.0, 4096)}


def test_integration_base_commune():
    """La base unifiée (onglet Base de données, résolution des en-têtes) connaît les instruments."""
    import database
    assert database.lookup_telescope('OHP T120')['focal_length_mm'] == 7232.0
    assert database.lookup_telescope('IRIS OHP')['diameter_mm'] == 500.0
    assert database.get_pixel_size('flipro0:PL0394113') == 13.5
    assert database.get_pixel_size('flipro0:PL1344016') == 9.0
    assert database.calculate_image_scale('OHP IRIS', 'FLI ProLine 2048') == pytest.approx(0.684, abs=0.001)


def _moteur():
    pytest.importorskip('astropy')
    try:
        import fits_analyser_gui
    except Exception as e:  # moteur historique : dépendances lourdes
        pytest.skip(f'moteur d\'analyse non importable ici : {e}')
    return fits_analyser_gui


def test_moteur_d_analyse_fits(tmp_path):
    """Un FITS réel (en-tête T120 Marana) passe par le moteur d'analyse et en ressort reconnu."""
    fag = _moteur()
    import numpy as np
    from astropy.io import fits
    h = fits.Header()
    for k, v in {'TELESCOP': 'OHP T120', 'INSTRUME': 'Andor sCMOS (SDK3)', 'APTDIA': 1200.0, 'FOCALLEN': 7200.0,
                 'XPIXSZ': 21.911, 'XBINNING': 2, 'EXPTIME': 8.0, 'FILTER': 'R'}.items():
        h[k] = v
    f = tmp_path / 'essai.fits'
    fits.PrimaryHDU(np.zeros((8, 8), dtype=np.uint16), header=h).writeto(f)
    with fits.open(f) as hdul:
        assert fag.get_telescope_from_header(hdul[0].header) == 'OHP T120'
        assert fag.get_instrument_from_header(hdul[0].header) == 'Andor Marana 4.2B-11'
    assert fag.get_telescope_characteristics('OHP T120')['focal_length_mm'] == 7232.0
    assert fag.get_sensor_characteristics('Andor Marana 4.2B-11')['pixel_size'] == 11.0


def test_moteur_d_analyse_xisf(tmp_path):
    """Un XISF réel (en-tête IRIS « ACP->NTM ») lu par le lecteur XISF de l'application est reconnu."""
    fag = _moteur()
    xisf = pytest.importorskip('xisf')
    import numpy as np
    entete = ENTETES_REELS['IRIS ProLine 2048, TELESCOP « ACP->NTM » (XML échappé)'][0]
    mots = {k: [{'value': v.replace('&gt;', '>'), 'comment': ''}] for k, v in entete.items() if k != 'NAXIS1'}
    f = tmp_path / 'essai.xisf'
    xisf.XISF.write(str(f), np.zeros((8, 8, 1), dtype=np.uint16), creator_app='essai',
                    image_metadata={'FITSKeywords': mots}, codec=None)
    with fag.open_fits_for_data(str(f), header_only=True) as hdul:
        h = hdul[0].header
        assert fag.get_telescope_from_header(h) == 'OHP IRIS'
        assert fag.get_instrument_from_header(h) == 'FLI ProLine 2048'
    _, h2 = fag.read_xisf_file(str(f))
    assert detect_observatory_equipment(h2)['camera'] == 'FLI ProLine 2048'
