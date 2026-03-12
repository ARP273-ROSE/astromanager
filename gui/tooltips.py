#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - TOOLTIP DEFINITIONS
================================================================================
Bilingual tooltip texts for PixInsight processing metrics.
================================================================================
"""

from core.i18n import get_lang


def _tr(en: str, fr: str) -> str:
    return fr if get_lang() == 'fr' else en


PIXINSIGHT_PROCESSING_TIPS = {
    'subframe_fwhm': lambda: _tr(
        "FWHM (Full Width at Half Maximum) in pixels.\n"
        "Measures star size/focus quality. Lower is better.\n"
        "< 3 px = excellent, 3-5 px = good, > 6 px = poor.",
        "FWHM (Full Width at Half Maximum) en pixels.\n"
        "Mesure la taille des étoiles / qualité de mise au point.\n"
        "Plus bas = meilleur. < 3 px = excellent, 3-5 px = bon, > 6 px = mauvais."
    ),
    'subframe_eccentricity': lambda: _tr(
        "Eccentricity measures star elongation.\n"
        "0 = perfect circle, 1 = very elongated.\n"
        "< 0.4 = good, 0.4-0.6 = acceptable, > 0.6 = poor tracking/guiding.",
        "L'excentricité mesure l'élongation des étoiles.\n"
        "0 = cercle parfait, 1 = très allongé.\n"
        "< 0.4 = bon, 0.4-0.6 = acceptable, > 0.6 = suivi/guidage médiocre."
    ),
    'subframe_snr': lambda: _tr(
        "Signal-to-Noise Ratio per frame.\n"
        "Higher values indicate better signal quality.\n"
        "Depends on exposure time, light pollution, and sky conditions.",
        "Rapport Signal/Bruit par image.\n"
        "Des valeurs plus élevées indiquent une meilleure qualité de signal.\n"
        "Dépend du temps d'exposition, de la pollution lumineuse et des conditions."
    ),
    'subframe_psf_weight': lambda: _tr(
        "PSF Signal Weight combines FWHM, eccentricity and SNR\n"
        "into a single quality score. Higher is better.\n"
        "Used by ImageIntegration for frame weighting.",
        "Le PSF Signal Weight combine FWHM, excentricité et SNR\n"
        "en un score de qualité unique. Plus haut = meilleur.\n"
        "Utilisé par ImageIntegration pour la pondération des images."
    ),
    'frame_rejection': lambda: _tr(
        "Frame rejection by SubframeSelector.\n"
        "Frames with weight below threshold are rejected.\n"
        "Rejected frames are excluded from integration.",
        "Rejet d'images par SubframeSelector.\n"
        "Les images avec un poids sous le seuil sont rejetées.\n"
        "Les images rejetées sont exclues de l'intégration."
    ),
    'pixel_rejection': lambda: _tr(
        "Pixel rejection during ImageIntegration.\n"
        "Removes outlier pixels (cosmic rays, satellites, hot pixels).\n"
        "Typical total rejection: 1-5%. Very high values may indicate issues.",
        "Rejet de pixels pendant l'ImageIntegration.\n"
        "Supprime les pixels aberrants (rayons cosmiques, satellites, pixels chauds).\n"
        "Rejet typique : 1-5 %. Des valeurs très élevées peuvent indiquer des problèmes."
    ),
    'integration_method': lambda: _tr(
        "ImageIntegration combination method.\n"
        "Average: best SNR, requires good rejection.\n"
        "Median: robust to outliers, lower SNR.",
        "Méthode de combinaison ImageIntegration.\n"
        "Average : meilleur SNR, nécessite un bon rejet.\n"
        "Median : robuste aux aberrants, SNR plus faible."
    ),
    'normalized_weight': lambda: _tr(
        "Normalized frame weight (0.0 - 1.0).\n"
        "1.0 = reference quality, lower = less contribution.\n"
        "Based on PSFSignalWeight or NoiseWeight mode.",
        "Poids normalisé de l'image (0.0 - 1.0).\n"
        "1.0 = qualité de référence, plus bas = moins de contribution.\n"
        "Basé sur le mode PSFSignalWeight ou NoiseWeight."
    ),
    'calibration_master': lambda: _tr(
        "Master calibration frames used:\n"
        "- Master Dark: thermal noise correction\n"
        "- Master Flat: vignetting & dust correction\n"
        "- Master Bias: readout noise correction",
        "Images maîtres de calibration utilisées :\n"
        "- Master Dark : correction du bruit thermique\n"
        "- Master Flat : correction du vignetage et poussières\n"
        "- Master Bias : correction du bruit de lecture"
    ),
    'quality_trend': lambda: _tr(
        "Quality trends across sessions.\n"
        "Track FWHM and SNR evolution over time\n"
        "to identify equipment or site improvements.",
        "Tendances de qualité entre sessions.\n"
        "Suivez l'évolution du FWHM et SNR dans le temps\n"
        "pour identifier les améliorations d'équipement ou de site."
    ),
    'filter_comparison': lambda: _tr(
        "Quality comparison between filters.\n"
        "Narrowband filters (Ha, OIII, SII) typically show\n"
        "higher FWHM due to longer focal length PSF sampling.",
        "Comparaison de qualité entre filtres.\n"
        "Les filtres narrowband (Ha, OIII, SII) montrent typiquement\n"
        "un FWHM plus élevé dû à l'échantillonnage PSF."
    ),
    'seeing_estimation': lambda: _tr(
        "Seeing estimation from FWHM.\n"
        "Seeing (arcsec) = FWHM (px) × pixel scale (arcsec/px).\n"
        "Requires known pixel scale for your setup.",
        "Estimation du seeing à partir du FWHM.\n"
        "Seeing (arcsec) = FWHM (px) × échelle pixel (arcsec/px).\n"
        "Nécessite l'échelle pixel connue pour votre setup."
    ),
}


MOUNT_TIPS = {
    'mount_ra_rms': lambda: _tr(
        "RA RMS deviation in arcseconds.\n"
        "Root Mean Square of RA tracking error.\n"
        "< 0.5\" = excellent, 0.5-1\" = good, > 2\" = poor.",
        "Déviation RMS RA en secondes d'arc.\n"
        "Racine carrée de l'erreur quadratique moyenne en RA.\n"
        "< 0.5\" = excellent, 0.5-1\" = bon, > 2\" = mauvais."
    ),
    'mount_dec_rms': lambda: _tr(
        "DEC RMS deviation in arcseconds.\n"
        "Root Mean Square of DEC tracking error.\n"
        "< 0.5\" = excellent, 0.5-1\" = good, > 2\" = poor.",
        "Déviation RMS DEC en secondes d'arc.\n"
        "Racine carrée de l'erreur quadratique moyenne en DEC.\n"
        "< 0.5\" = excellent, 0.5-1\" = bon, > 2\" = mauvais."
    ),
    'mount_tracking_pct': lambda: _tr(
        "Percentage of samples in TRACKING state.\n"
        "Excludes SLEWING, PARKED, and IDLE states.\n"
        "Higher = more useful data for analysis.",
        "Pourcentage d'échantillons en état TRACKING.\n"
        "Exclut les états SLEWING, PARKED et IDLE.\n"
        "Plus élevé = plus de données utiles pour l'analyse."
    ),
    'mount_total_samples': lambda: _tr(
        "Total number of data samples recorded.\n"
        "Includes all mount states (tracking, slewing, parked).\n"
        "Sampling rate depends on MountMonitor settings.",
        "Nombre total d'échantillons enregistrés.\n"
        "Inclut tous les états de la monture.\n"
        "La cadence dépend des réglages MountMonitor."
    ),
    'mount_quality_rating': lambda: _tr(
        "Overall tracking quality grade (A-F).\n"
        "A: < 0.5\" RMS (excellent)\n"
        "B: < 1.0\" (good) | C: < 2.0\" (fair)\n"
        "D: < 5.0\" (poor) | F: >= 5.0\" (very poor)",
        "Note globale de qualité de suivi (A-F).\n"
        "A : < 0.5\" RMS (excellent)\n"
        "B : < 1.0\" (bon) | C : < 2.0\" (correct)\n"
        "D : < 5.0\" (médiocre) | F : >= 5.0\" (très mauvais)"
    ),
    'mount_pe_period': lambda: _tr(
        "Dominant periodic error period from FFT analysis.\n"
        "Typically corresponds to worm gear period.\n"
        "Common values: 480s (8min) for many mounts.",
        "Période dominante de l'erreur périodique (FFT).\n"
        "Correspond typiquement à la période de la vis sans fin.\n"
        "Valeurs courantes : 480s (8min) pour beaucoup de montures."
    ),
    'mount_tracking_chart': lambda: _tr(
        "Timeline of RA/DEC tracking deviations.\n"
        "Shows how the mount tracks over time.\n"
        "RA deviations include cos(dec) correction.",
        "Chronologie des déviations de suivi RA/DEC.\n"
        "Montre comment la monture suit dans le temps.\n"
        "Les déviations RA incluent la correction cos(dec)."
    ),
    'mount_fft_chart': lambda: _tr(
        "FFT frequency analysis of tracking error.\n"
        "Peaks indicate periodic mechanical errors.\n"
        "Dominant peaks reveal worm gear frequency.",
        "Analyse fréquentielle FFT de l'erreur de suivi.\n"
        "Les pics indiquent des erreurs mécaniques périodiques.\n"
        "Les pics dominants révèlent la fréquence de la vis sans fin."
    ),
    'mount_segments_table': lambda: _tr(
        "Tracking statistics per detected target.\n"
        "Targets are detected by RA/DEC jumps.\n"
        "Each row shows stats for one pointing position.",
        "Statistiques de suivi par cible détectée.\n"
        "Les cibles sont détectées par sauts RA/DEC.\n"
        "Chaque ligne montre les stats pour une position."
    ),
    'mount_cos_dec': lambda: _tr(
        "RA deviations are corrected for cos(declination).\n"
        "At high declinations, RA arcseconds on the sky\n"
        "are smaller than at the celestial equator.",
        "Les déviations RA sont corrigées par cos(déclinaison).\n"
        "À hautes déclinaisons, les secondes d'arc en RA sur le ciel\n"
        "sont plus petites qu'à l'équateur céleste."
    ),
    'mount_import': lambda: _tr(
        "Import MountMonitor .dat log file.\n"
        "Companion files (.dti, .fft, .env, .log)\n"
        "are automatically detected and parsed.",
        "Importer un fichier log MountMonitor .dat.\n"
        "Les fichiers associés (.dti, .fft, .env, .log)\n"
        "sont automatiquement détectés et analysés."
    ),
    'mount_import_folder': lambda: _tr(
        "Import all MountMonitor logs from a folder.\n"
        "Scans for MountMonitor_*.dat files\n"
        "and imports each with its companion files.",
        "Importer tous les logs MountMonitor d'un dossier.\n"
        "Recherche les fichiers MountMonitor_*.dat\n"
        "et importe chacun avec ses fichiers associés."
    ),
    'mount_session_selector': lambda: _tr(
        "Select a MountMonitor session to analyze.\n"
        "Each session corresponds to one recording.\n"
        "Sessions are listed by date, most recent first.",
        "Sélectionner une session MountMonitor à analyser.\n"
        "Chaque session correspond à un enregistrement.\n"
        "Classées par date, plus récente en premier."
    ),
    'mount_time_stability': lambda: _tr(
        "PC-Mount clock synchronization stability.\n"
        "Large drift indicates timing issues.\n"
        "Loop times show communication latency.",
        "Stabilité de synchronisation horloge PC-Monture.\n"
        "Une dérive importante indique des problèmes de timing.\n"
        "Les temps de boucle montrent la latence de communication."
    ),
    'mount_environment': lambda: _tr(
        "Environment conditions during session.\n"
        "Temperature, pressure, pier side, alignment data.\n"
        "Correlate with tracking quality.",
        "Conditions environnementales pendant la session.\n"
        "Température, pression, côté du pilier, données d'alignement.\n"
        "À corréler avec la qualité de suivi."
    ),
}


def get_tip(key: str) -> str:
    """Get a tooltip text by key. Returns empty string if not found."""
    tip_fn = PIXINSIGHT_PROCESSING_TIPS.get(key)
    if tip_fn:
        return tip_fn()
    tip_fn = MOUNT_TIPS.get(key)
    if tip_fn:
        return tip_fn()
    return ''
