#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - TARGET CLUSTERING MODULE
================================================================================
Clusters astrophotography targets by celestial coordinates using DBSCAN to
identify potential duplicates or related objects in the same field.

Uses the Haversine formula for great-circle angular distance on the celestial
sphere, and DBSCAN clustering via scipy (with brute-force fallback).

Features:
  - DBSCAN clustering on RA/Dec with cos(dec) correction
  - Haversine angular distance metric for proper spherical geometry
  - Merge suggestions for likely duplicate targets
  - Nearby-target search by coordinates
  - Cluster statistics summary
  - Merge helper (moves observations, deletes source target)
================================================================================
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.database import get_db

logger = logging.getLogger(__name__)

# Try to import scipy for efficient clustering; fall back to brute-force
try:
    from scipy.spatial.distance import pdist, squareform
    from scipy.cluster.hierarchy import fclusterdata
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not available — using brute-force pairwise clustering")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TargetCluster:
    """A cluster of spatially close targets on the celestial sphere."""
    cluster_id: int
    targets: list = field(default_factory=list)   # list of target dicts from DB
    center_ra: float = 0.0                        # hours (0-24)
    center_dec: float = 0.0                       # degrees (-90 to +90)
    radius: float = 0.0                           # degrees, max angular distance from center
    total_exposure: float = 0.0                    # seconds
    total_frames: int = 0
    suggested_name: str = ""                       # target with most exposure time
    merge_suggestion: bool = False                 # True if targets likely same object


# ---------------------------------------------------------------------------
# Angular distance (Haversine)
# ---------------------------------------------------------------------------

def angular_distance(ra1_h: float, dec1_d: float,
                     ra2_h: float, dec2_d: float) -> float:
    """
    Compute the great-circle angular distance between two sky positions
    using the Haversine formula.

    Parameters
    ----------
    ra1_h, ra2_h : float
        Right Ascension in hours (0-24).
    dec1_d, dec2_d : float
        Declination in degrees (-90 to +90).

    Returns
    -------
    float
        Angular separation in degrees.
    """
    # Convert RA hours -> radians, Dec degrees -> radians
    ra1 = math.radians(ra1_h * 15.0)
    ra2 = math.radians(ra2_h * 15.0)
    dec1 = math.radians(dec1_d)
    dec2 = math.radians(dec2_d)

    d_ra = ra2 - ra1
    d_dec = dec2 - dec1

    a = (math.sin(d_dec / 2.0) ** 2
         + math.cos(dec1) * math.cos(dec2) * math.sin(d_ra / 2.0) ** 2)
    # Clamp to [0, 1] for numerical safety
    a = max(0.0, min(1.0, a))
    c = 2.0 * math.asin(math.sqrt(a))

    return math.degrees(c)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_targets_with_coords() -> List[Dict]:
    """Load all targets that have valid RA and Dec from the database."""
    db = get_db()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, canonical_name, ra, dec, object_type,
                   total_exposure_time, total_frames
            FROM targets
            WHERE ra IS NOT NULL AND dec IS NOT NULL
            ORDER BY id
        """)
        return [dict(row) for row in cursor.fetchall()]


def _name_similarity(name_a: str, name_b: str) -> bool:
    """
    Check whether two target names likely refer to the same object.

    Uses simple substring / alias matching for common catalogue designations
    (e.g. M31 and NGC 224, NGC0224, etc.).
    """
    if not name_a or not name_b:
        return False

    a = name_a.strip().upper().replace(" ", "").replace("-", "").replace("_", "")
    b = name_b.strip().upper().replace(" ", "").replace("-", "").replace("_", "")

    # Direct substring containment (handles "M31" in "M31 - Andromeda")
    if a in b or b in a:
        return True

    # Strip leading zeros from catalogue numbers (NGC0224 == NGC224)
    def _normalise_catalogue(s: str) -> str:
        for prefix in ("NGC", "IC", "M", "ARP", "SH2", "LDN", "LBN",
                       "UGC", "PGC", "VDB", "CED", "ABELL"):
            if s.startswith(prefix):
                num = s[len(prefix):].lstrip("0")
                return prefix + num
        return s

    return _normalise_catalogue(a) == _normalise_catalogue(b)


def _compute_cluster_center(targets: List[Dict]) -> Tuple[float, float]:
    """
    Compute the mean RA/Dec of a set of targets.

    Uses Cartesian averaging to handle the RA wrap-around at 0h/24h correctly.
    """
    if not targets:
        return 0.0, 0.0

    # Convert to Cartesian, average, convert back
    x_sum = y_sum = z_sum = 0.0
    for t in targets:
        ra_rad = math.radians(t["ra"] * 15.0)
        dec_rad = math.radians(t["dec"])
        x_sum += math.cos(dec_rad) * math.cos(ra_rad)
        y_sum += math.cos(dec_rad) * math.sin(ra_rad)
        z_sum += math.sin(dec_rad)

    n = len(targets)
    x_avg, y_avg, z_avg = x_sum / n, y_sum / n, z_sum / n

    dec_avg = math.degrees(math.atan2(z_avg, math.sqrt(x_avg ** 2 + y_avg ** 2)))
    ra_avg_deg = math.degrees(math.atan2(y_avg, x_avg)) % 360.0
    ra_avg_h = ra_avg_deg / 15.0

    return ra_avg_h, dec_avg


def _build_distance_matrix_bruteforce(targets: List[Dict]) -> List[List[float]]:
    """Build a full pairwise distance matrix using pure Python (no scipy)."""
    n = len(targets)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = angular_distance(
                targets[i]["ra"], targets[i]["dec"],
                targets[j]["ra"], targets[j]["dec"],
            )
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix


def _dbscan_bruteforce(targets: List[Dict], epsilon_deg: float,
                       min_samples: int) -> List[int]:
    """
    Simple DBSCAN implementation for when scipy is not available.

    Returns a list of cluster labels (0-based). Noise points get label -1.
    """
    n = len(targets)
    if n == 0:
        return []

    dist = _build_distance_matrix_bruteforce(targets)
    labels = [-1] * n
    cluster_id = 0

    visited = [False] * n

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True

        # Find neighbours
        neighbours = [j for j in range(n) if dist[i][j] <= epsilon_deg]

        if len(neighbours) < min_samples:
            continue  # noise

        # Expand cluster
        labels[i] = cluster_id
        seed_set = list(neighbours)
        k = 0
        while k < len(seed_set):
            q = seed_set[k]
            if not visited[q]:
                visited[q] = True
                q_neighbours = [j for j in range(n) if dist[q][j] <= epsilon_deg]
                if len(q_neighbours) >= min_samples:
                    for nb in q_neighbours:
                        if nb not in seed_set:
                            seed_set.append(nb)
            if labels[q] == -1:
                labels[q] = cluster_id
            k += 1

        cluster_id += 1

    return labels


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def cluster_targets(epsilon_deg: float = 0.5,
                    min_samples: int = 1) -> List[TargetCluster]:
    """
    Cluster all targets with valid coordinates using DBSCAN.

    Parameters
    ----------
    epsilon_deg : float
        Maximum angular separation (degrees) to consider targets as neighbours.
        Default 0.5 deg (30 arcmin — a typical large object field of view).
    min_samples : int
        Minimum number of targets to form a cluster.  Default 1 (every target
        belongs to at least its own cluster).

    Returns
    -------
    list[TargetCluster]
        Clusters sorted by cluster_id.
    """
    targets = _load_targets_with_coords()
    if not targets:
        return []

    n = len(targets)
    logger.info("Clustering %d targets (eps=%.3f deg, min_samples=%d)",
                n, epsilon_deg, min_samples)

    # --- Compute cluster labels ---
    if SCIPY_AVAILABLE and NUMPY_AVAILABLE and n >= 2:
        # Build condensed distance vector via pdist with custom metric
        coords = [(t["ra"], t["dec"]) for t in targets]
        dist_vec = pdist(coords,
                         metric=lambda u, v: angular_distance(u[0], u[1],
                                                              v[0], v[1]))
        dist_matrix = squareform(dist_vec)

        # Use fclusterdata-style approach: hierarchical with distance threshold
        # For true DBSCAN behaviour we replicate the algorithm on the distance
        # matrix, since scipy.cluster.hierarchy doesn't natively do DBSCAN.
        labels = _dbscan_from_matrix(dist_matrix, epsilon_deg, min_samples)
    elif n >= 2:
        labels = _dbscan_bruteforce(targets, epsilon_deg, min_samples)
    else:
        labels = [0]

    # --- Build TargetCluster objects ---
    clusters_map: Dict[int, List[Dict]] = {}
    for idx, lbl in enumerate(labels):
        if lbl == -1:
            # Noise — put each in its own singleton cluster
            singleton_id = max(clusters_map.keys(), default=-1) + 1
            clusters_map[singleton_id] = [targets[idx]]
        else:
            clusters_map.setdefault(lbl, []).append(targets[idx])

    result: List[TargetCluster] = []
    for cid, members in sorted(clusters_map.items()):
        center_ra, center_dec = _compute_cluster_center(members)

        # Radius: max distance from center to any member
        radius = 0.0
        for t in members:
            d = angular_distance(center_ra, center_dec, t["ra"], t["dec"])
            radius = max(radius, d)

        total_exp = sum(t.get("total_exposure_time") or 0.0 for t in members)
        total_fr = sum(t.get("total_frames") or 0 for t in members)

        # Suggested name = target with the most exposure time
        best = max(members,
                   key=lambda t: (t.get("total_exposure_time") or 0.0))
        suggested = best.get("canonical_name") or best.get("name", "")

        # Merge suggestion heuristic
        merge = _should_suggest_merge(members)

        result.append(TargetCluster(
            cluster_id=cid,
            targets=members,
            center_ra=center_ra,
            center_dec=center_dec,
            radius=radius,
            total_exposure=total_exp,
            total_frames=total_fr,
            suggested_name=suggested,
            merge_suggestion=merge,
        ))

    logger.info("Found %d clusters from %d targets", len(result), n)
    return result


def _dbscan_from_matrix(dist_matrix, epsilon_deg: float,
                        min_samples: int) -> List[int]:
    """Run DBSCAN on a precomputed numpy distance matrix."""
    n = dist_matrix.shape[0]
    labels = [-1] * n
    visited = [False] * n
    cluster_id = 0

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True

        neighbours = list(np.where(dist_matrix[i] <= epsilon_deg)[0])

        if len(neighbours) < min_samples:
            continue

        labels[i] = cluster_id
        seed_set = list(neighbours)
        k = 0
        while k < len(seed_set):
            q = seed_set[k]
            if not visited[q]:
                visited[q] = True
                q_nb = list(np.where(dist_matrix[q] <= epsilon_deg)[0])
                if len(q_nb) >= min_samples:
                    for nb in q_nb:
                        if nb not in seed_set:
                            seed_set.append(nb)
            if labels[q] == -1:
                labels[q] = cluster_id
            k += 1

        cluster_id += 1

    return labels


def _should_suggest_merge(members: List[Dict]) -> bool:
    """
    Decide whether a cluster's members are likely the same object.

    Rules:
    - Single target → no merge needed.
    - Any pair within 5 arcmin → strong merge suggestion.
    - Any pair within 15 arcmin with similar names → moderate suggestion.
    """
    if len(members) <= 1:
        return False

    STRONG_ARCMIN = 5.0
    MODERATE_ARCMIN = 15.0

    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            dist = angular_distance(
                members[i]["ra"], members[i]["dec"],
                members[j]["ra"], members[j]["dec"],
            )
            dist_arcmin = dist * 60.0

            if dist_arcmin <= STRONG_ARCMIN:
                return True

            if dist_arcmin <= MODERATE_ARCMIN:
                name_i = (members[i].get("canonical_name")
                          or members[i].get("name", ""))
                name_j = (members[j].get("canonical_name")
                          or members[j].get("name", ""))
                if _name_similarity(name_i, name_j):
                    return True

    return False


def find_nearby_targets(ra_hours: float, dec_deg: float,
                        radius_deg: float = 1.0) -> List[Dict]:
    """
    Find all targets within a given angular radius of the specified coordinates.

    Parameters
    ----------
    ra_hours : float
        Right Ascension in hours (0-24).
    dec_deg : float
        Declination in degrees (-90 to +90).
    radius_deg : float
        Search radius in degrees. Default 1.0.

    Returns
    -------
    list[dict]
        Target dicts with an extra ``"distance_deg"`` key, sorted by distance.
    """
    targets = _load_targets_with_coords()
    results = []

    for t in targets:
        d = angular_distance(ra_hours, dec_deg, t["ra"], t["dec"])
        if d <= radius_deg:
            t_copy = dict(t)
            t_copy["distance_deg"] = round(d, 6)
            results.append(t_copy)

    results.sort(key=lambda x: x["distance_deg"])
    return results


def suggest_merges(clusters: Optional[List[TargetCluster]] = None) -> List[Dict]:
    """
    Return a list of merge suggestions from clustering results.

    Each suggestion is a dict with:
      - ``source``: target dict (the one to merge away)
      - ``dest``: target dict (the one to keep — most exposure)
      - ``distance_arcmin``: angular distance between them
      - ``name_match``: bool, whether names appear related
      - ``strength``: ``"strong"`` (< 5') or ``"moderate"`` (< 15' + name match)

    Parameters
    ----------
    clusters : list[TargetCluster] or None
        Pre-computed clusters.  If None, runs ``cluster_targets()`` first.
    """
    if clusters is None:
        clusters = cluster_targets()

    suggestions: List[Dict] = []

    for cl in clusters:
        if len(cl.targets) <= 1 or not cl.merge_suggestion:
            continue

        # Sort by exposure descending — first target is the "keep" target
        sorted_targets = sorted(
            cl.targets,
            key=lambda t: (t.get("total_exposure_time") or 0.0),
            reverse=True,
        )
        dest = sorted_targets[0]

        for source in sorted_targets[1:]:
            dist = angular_distance(
                source["ra"], source["dec"],
                dest["ra"], dest["dec"],
            )
            dist_arcmin = dist * 60.0

            name_src = (source.get("canonical_name")
                        or source.get("name", ""))
            name_dst = (dest.get("canonical_name")
                        or dest.get("name", ""))
            name_match = _name_similarity(name_src, name_dst)

            if dist_arcmin <= 5.0:
                strength = "strong"
            elif dist_arcmin <= 15.0 and name_match:
                strength = "moderate"
            else:
                continue

            suggestions.append({
                "source": source,
                "dest": dest,
                "distance_arcmin": round(dist_arcmin, 2),
                "name_match": name_match,
                "strength": strength,
            })

    suggestions.sort(key=lambda s: s["distance_arcmin"])
    return suggestions


def merge_targets(source_id: int, dest_id: int,
                  dry_run: bool = True) -> Dict:
    """
    Merge source target into destination target.

    Moves all observations from source to dest, accumulates exposure stats,
    then deletes the source target.

    Parameters
    ----------
    source_id : int
        Target ID to merge away (will be deleted).
    dest_id : int
        Target ID to keep.
    dry_run : bool
        If True (default), only report what would change without modifying
        the database.

    Returns
    -------
    dict
        Summary with keys: ``source``, ``dest``, ``observations_moved``,
        ``applied`` (bool).
    """
    db = get_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Fetch both targets
        cursor.execute("SELECT * FROM targets WHERE id = ?", (source_id,))
        source = cursor.fetchone()
        cursor.execute("SELECT * FROM targets WHERE id = ?", (dest_id,))
        dest = cursor.fetchone()

        if not source:
            raise ValueError(f"Source target id={source_id} not found")
        if not dest:
            raise ValueError(f"Destination target id={dest_id} not found")

        source = dict(source)
        dest = dict(dest)

        # Count observations to move
        cursor.execute(
            "SELECT COUNT(*) FROM observations WHERE target_id = ?",
            (source_id,),
        )
        obs_count = cursor.fetchone()[0]

        summary = {
            "source": {
                "id": source["id"],
                "name": source["name"],
                "exposure": source.get("total_exposure_time") or 0,
                "frames": source.get("total_frames") or 0,
            },
            "dest": {
                "id": dest["id"],
                "name": dest["name"],
                "exposure": dest.get("total_exposure_time") or 0,
                "frames": dest.get("total_frames") or 0,
            },
            "observations_moved": obs_count,
            "applied": False,
        }

        if dry_run:
            return summary

        # Move observations
        cursor.execute(
            "UPDATE observations SET target_id = ? WHERE target_id = ?",
            (dest_id, source_id),
        )

        # Delete source target
        cursor.execute("DELETE FROM targets WHERE id = ?", (source_id,))

        # Recalculate dest stats
        cursor.execute("""
            SELECT COALESCE(SUM(exposure_time), 0),
                   COALESCE(SUM(frame_count), 0),
                   MIN(observation_date),
                   MAX(observation_date)
            FROM observations WHERE target_id = ?
        """, (dest_id,))
        row = cursor.fetchone()
        cursor.execute("""
            UPDATE targets SET
                total_exposure_time = ?,
                total_frames = ?,
                first_observed = ?,
                last_observed = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (row[0], row[1], row[2], row[3], dest_id))

        summary["applied"] = True
        logger.info("Merged target '%s' (id=%d) into '%s' (id=%d) — %d observations moved",
                     source["name"], source_id, dest["name"], dest_id, obs_count)

    return summary


def get_cluster_stats() -> Dict:
    """
    Return summary statistics about target clustering.

    Returns
    -------
    dict
        Keys: ``total_targets``, ``clustered_targets``, ``num_clusters``,
        ``singletons``, ``multi_target_clusters``, ``merge_candidates``,
        ``largest_cluster_size``, ``avg_cluster_radius_arcmin``.
    """
    clusters = cluster_targets()

    total = sum(len(c.targets) for c in clusters)
    singletons = sum(1 for c in clusters if len(c.targets) == 1)
    multi = sum(1 for c in clusters if len(c.targets) > 1)
    merge_candidates = sum(1 for c in clusters if c.merge_suggestion)
    largest = max((len(c.targets) for c in clusters), default=0)

    radii = [c.radius * 60.0 for c in clusters if len(c.targets) > 1]
    avg_radius = sum(radii) / len(radii) if radii else 0.0

    return {
        "total_targets": total,
        "clustered_targets": total - singletons,
        "num_clusters": len(clusters),
        "singletons": singletons,
        "multi_target_clusters": multi,
        "merge_candidates": merge_candidates,
        "largest_cluster_size": largest,
        "avg_cluster_radius_arcmin": round(avg_radius, 2),
    }
