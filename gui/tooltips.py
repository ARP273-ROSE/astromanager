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


ANALYTICS_TIPS = {
    'nina_import_folder': lambda: _tr(
        "Select the root folder containing N.I.N.A. session data.\n"
        "The importer will recursively find ImageMetaData.csv\n"
        "and WeatherData.csv files in all subdirectories.",
        "Sélectionnez le dossier racine contenant les sessions N.I.N.A.\n"
        "L'importeur cherchera récursivement les fichiers ImageMetaData.csv\n"
        "et WeatherData.csv dans tous les sous-dossiers."
    ),
    'nina_import_btn': lambda: _tr(
        "Start importing N.I.N.A. CSV metadata.\n"
        "Parses exposure metrics (HFR, FWHM, guiding, ADU)\n"
        "and weather data, then stores them in the database.",
        "Lancer l'import des métadonnées CSV N.I.N.A.\n"
        "Parse les métriques d'exposition (HFR, FWHM, guidage, ADU)\n"
        "et les données météo, puis les stocke en base."
    ),
    'efficiency_chart': lambda: _tr(
        "Imaging efficiency = integration time / astronomical dark hours.\n"
        "Dark hours = sun below -18° (astronomical twilight).\n"
        "Higher percentage means more productive sessions.",
        "Efficacité d'imagerie = temps d'intégration / heures d'obscurité.\n"
        "Heures sombres = soleil sous -18° (crépuscule astronomique).\n"
        "Un pourcentage plus élevé = sessions plus productives."
    ),
    'correlation_x': lambda: _tr(
        "Select the X-axis metric for correlation analysis.\n"
        "Environmental metrics: temperature, humidity, wind, cloud cover.\n"
        "Equipment: focuser temperature, airmass, sensor temperature.",
        "Sélectionnez la métrique X pour l'analyse de corrélation.\n"
        "Métriques environnementales : température, humidité, vent, couverture nuageuse.\n"
        "Équipement : température focuser, masse d'air, température capteur."
    ),
    'correlation_y': lambda: _tr(
        "Select the Y-axis metric for correlation analysis.\n"
        "Quality metrics: HFR, FWHM, eccentricity, guiding RMS.\n"
        "Signal metrics: detected stars, ADU mean/median.",
        "Sélectionnez la métrique Y pour l'analyse de corrélation.\n"
        "Métriques qualité : HFR, FWHM, excentricité, RMS guidage.\n"
        "Métriques signal : étoiles détectées, ADU moyen/médian."
    ),
    'correlation_chart': lambda: _tr(
        "Scatter plot with linear regression line.\n"
        "Shows Pearson r, Spearman ρ, R² and 95% confidence band.\n"
        "Filter by telescope, camera, filter, or date range.",
        "Nuage de points avec droite de régression linéaire.\n"
        "Affiche Pearson r, Spearman ρ, R² et bande de confiance 95%.\n"
        "Filtrez par télescope, caméra, filtre ou période."
    ),
    'timeseries_metric': lambda: _tr(
        "Select a metric to plot over time.\n"
        "Shows nightly median with 7-day and 30-day moving averages.\n"
        "Useful to track equipment performance trends.",
        "Sélectionnez une métrique à tracer dans le temps.\n"
        "Affiche la médiane nocturne avec moyennes mobiles 7j et 30j.\n"
        "Utile pour suivre les tendances de performance de l'équipement."
    ),
    'equipment_table': lambda: _tr(
        "Performance statistics per telescope+camera+filter combination.\n"
        "Shows median HFR, FWHM, eccentricity, best HFR, and frame count.\n"
        "Helps identify your best-performing equipment setups.",
        "Statistiques de performance par combinaison télescope+caméra+filtre.\n"
        "Affiche HFR médian, FWHM, excentricité, meilleur HFR, nombre de frames.\n"
        "Aide à identifier vos configurations d'équipement les plus performantes."
    ),
    'session_note_date': lambda: _tr(
        "Select the observation date for this note.\n"
        "Notes are stored per session date.",
        "Sélectionnez la date d'observation pour cette note.\n"
        "Les notes sont stockées par date de session."
    ),
    'session_note_text': lambda: _tr(
        "Write observation notes for this session.\n"
        "Equipment changes, weather conditions, issues encountered.\n"
        "Notes are saved automatically.",
        "Écrivez vos notes d'observation pour cette session.\n"
        "Changements d'équipement, conditions météo, problèmes rencontrés.\n"
        "Les notes sont sauvegardées automatiquement."
    ),
    'nina_progress': lambda: _tr(
        "Import progress for the current N.I.N.A. data import.\n"
        "Shows percentage of CSV files processed.",
        "Progression de l'import des données N.I.N.A. en cours.\n"
        "Affiche le pourcentage de fichiers CSV traités."
    ),
    'nina_table': lambda: _tr(
        "Summary of imported N.I.N.A. sessions.\n"
        "Shows date, frame count, targets, integration time,\n"
        "average HFR, filters used, and equipment.",
        "Résumé des sessions N.I.N.A. importées.\n"
        "Affiche date, nombre de frames, cibles, temps d'intégration,\n"
        "HFR moyen, filtres utilisés et équipement."
    ),
    'ts_plot_btn': lambda: _tr(
        "Plot the selected metric over time.\n"
        "Shows nightly median with 7-day and 30-day moving averages.",
        "Tracer la métrique sélectionnée dans le temps.\n"
        "Affiche la médiane nocturne avec moyennes mobiles 7j et 30j."
    ),
    'note_target_combo': lambda: _tr(
        "Select a specific target for this note,\n"
        "or '(All / General)' for session-wide notes.",
        "Sélectionnez une cible spécifique pour cette note,\n"
        "ou '(Tous / Général)' pour les notes de session."
    ),
    'notes_table': lambda: _tr(
        "List of all saved session notes.\n"
        "Click a row to load the note for editing.",
        "Liste de toutes les notes de session sauvegardées.\n"
        "Cliquez sur une ligne pour charger la note à modifier."
    ),
}

IMAGE_VIEWER_TIPS = {
    'iv_browse': lambda: _tr(
        "Browse for a folder containing FITS/XISF images.\n"
        "Scans recursively, excludes analysis output folders.",
        "Parcourir un dossier contenant des images FITS/XISF.\n"
        "Scan récursif, exclut les dossiers de sortie d'analyse."
    ),
    'iv_sort': lambda: _tr(
        "Sort file list by: name, date, or FWHM.\n"
        "Click again to reverse order.",
        "Trier la liste par : nom, date ou FWHM.\n"
        "Cliquez à nouveau pour inverser l'ordre."
    ),
    'iv_stf': lambda: _tr(
        "Toggle PixInsight-style auto-stretch (STF).\n"
        "Uses MAD shadow clipping + midtone transfer function.\n"
        "Display only — measurements always use raw data.",
        "Activer/désactiver l'auto-stretch style PixInsight (STF).\n"
        "Utilise clipping ombre MAD + fonction de transfert tons moyens.\n"
        "Affichage uniquement — les mesures utilisent toujours les données brutes."
    ),
    'iv_fwhm_map': lambda: _tr(
        "Toggle FWHM heatmap overlay on the image.\n"
        "Green = good focus, yellow = moderate, red = poor.\n"
        "Shows focus quality variation across the field.",
        "Activer/désactiver la heatmap FWHM sur l'image.\n"
        "Vert = bon focus, jaune = moyen, rouge = mauvais.\n"
        "Montre la variation de qualité du focus sur le champ."
    ),
    'iv_stars': lambda: _tr(
        "Toggle star detection overlay.\n"
        "Shows detected stars with FWHM labels.\n"
        "Circle color indicates quality (green=good, red=poor).",
        "Activer/désactiver la couche de détection d'étoiles.\n"
        "Affiche les étoiles détectées avec labels FWHM.\n"
        "La couleur du cercle indique la qualité (vert=bon, rouge=mauvais)."
    ),
    'iv_corners': lambda: _tr(
        "Toggle 3×3 corner inspector grid.\n"
        "Shows 9 crops at 100% zoom with per-cell FWHM statistics.\n"
        "Equalized backgrounds for easy visual comparison.",
        "Activer/désactiver la grille d'inspection 3×3.\n"
        "Affiche 9 recadrages à 100% zoom avec FWHM par cellule.\n"
        "Fonds égalisés pour une comparaison visuelle facile."
    ),
}

CROSS_SECTION_TIPS = {
    'cs_image1': lambda: _tr(
        "Load the reference image (Image 1).\n"
        "Supports FITS, XISF formats.\n"
        "This is the base image for comparison.",
        "Charger l'image de référence (Image 1).\n"
        "Supporte les formats FITS, XISF.\n"
        "C'est l'image de base pour la comparaison."
    ),
    'cs_image2': lambda: _tr(
        "Load the comparison image (Image 2).\n"
        "Should be the same field with different settings.\n"
        "Images will be auto-cropped to common size.",
        "Charger l'image de comparaison (Image 2).\n"
        "Doit être le même champ avec des réglages différents.\n"
        "Les images seront recadrées à la taille commune."
    ),
    'cs_mode': lambda: _tr(
        "Select interaction mode:\n"
        "• Line Profile: draw a line to plot intensity cross-section\n"
        "• Signal Region: select area containing the target signal\n"
        "• Background Region: select area for background subtraction",
        "Sélectionner le mode d'interaction :\n"
        "• Profil Ligne : tracer une ligne pour la coupe d'intensité\n"
        "• Région Signal : sélectionner la zone contenant le signal\n"
        "• Région Fond : sélectionner la zone pour la soustraction de fond"
    ),
    'cs_color': lambda: _tr(
        "Color mode for line profile:\n"
        "Luminance (BT.709), Red, Green, Blue, or all RGB channels.",
        "Mode couleur pour le profil de ligne :\n"
        "Luminance (BT.709), Rouge, Vert, Bleu, ou tous les canaux RGB."
    ),
    'cs_align': lambda: _tr(
        "Automatically align Image 2 to Image 1.\n"
        "Uses astroalign for star-based registration.\n"
        "Reports shift magnitude and rotation angle.",
        "Aligner automatiquement l'Image 2 sur l'Image 1.\n"
        "Utilise astroalign pour le recalage par étoiles.\n"
        "Rapporte l'amplitude du décalage et l'angle de rotation."
    ),
    'cs_export': lambda: _tr(
        "Export cross-section profiles and analysis to CSV.\n"
        "Includes distance, intensity values, and histograms.",
        "Exporter les profils de coupe et l'analyse en CSV.\n"
        "Inclut distance, valeurs d'intensité et histogrammes."
    ),
}


def get_tip(key: str) -> str:
    """Get a tooltip text by key. Returns empty string if not found."""
    for tips_dict in (PIXINSIGHT_PROCESSING_TIPS, MOUNT_TIPS,
                      ANALYTICS_TIPS, IMAGE_VIEWER_TIPS, CROSS_SECTION_TIPS):
        tip_fn = tips_dict.get(key)
        if tip_fn:
            return tip_fn()
    return ''
