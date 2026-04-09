#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
ASTROMANAGER - ENHANCED TARGET RESOLUTION MODULE
================================================================================
Multi-source astronomical target resolution with cascading fallback chain:
  1. Local database (AstroManager targets + observations)
  2. SIMBAD (via astroquery, feature-gated)
  3. SESAME (CDS XML service, stdlib HTTP)
  4. VizieR TAP (obscure catalogs: Sharpless, LBN, Barnard, RCW, etc.)

Returns standardized target metadata: coordinates, type, magnitude, size,
catalog identifiers, aliases, and description.
================================================================================
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import quote_plus, urlencode

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Safe XML parsing: prefer defusedxml for XXE protection, fallback to stdlib
# ---------------------------------------------------------------------------
try:
    from defusedxml.ElementTree import fromstring as _xml_fromstring
    _XML_SAFE = True
except ImportError:
    from xml.etree.ElementTree import fromstring as _xml_fromstring
    _XML_SAFE = False

# Always need stdlib for tree building (defusedxml only wraps parsing)
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Feature gate: astroquery (optional)
# ---------------------------------------------------------------------------
_HAS_ASTROQUERY = False
try:
    from astroquery.simbad import Simbad as _AstroquerySimbad
    _HAS_ASTROQUERY = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# SESAME endpoint (CDS multi-resolver: NED + SIMBAD + VizieR)
SESAME_URL = "https://cdsweb.u-strasbg.fr/cgi-bin/nph-sesame/-ox"

# VizieR TAP sync endpoint
VIZIER_TAP_URL = "https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync"

# HTTP timeouts (seconds)
SESAME_TIMEOUT = 10
VIZIER_TIMEOUT = 15
SIMBAD_TIMEOUT = 10

# User-Agent for HTTP requests
USER_AGENT = "AstroManager/1.1 (target-resolver)"

# Catalog prefix priority (lower = more common / preferred)
CATALOG_PRIORITY = {
    'M':        1,
    'NGC':      2,
    'IC':       3,
    'CALDWELL': 4,
    'C':        4,
    'SH2':      5,
    'ABELL':    6,
    'ARP':      7,
    'BARNARD':  8,
    'B':        8,
    'LBN':      9,
    'PGC':      10,
    'VDB':      11,
    'LDN':      12,
    'RCW':      13,
    'CED':      14,
}

# VizieR catalog table references for obscure catalogs
VIZIER_CATALOGS = {
    'Sharpless': {'table': '"VII/20/catalog"', 'name_col': 'Name'},
    'LBN':       {'table': '"VII/9/catalog"',  'name_col': 'Name'},
    'Barnard':   {'table': '"VII/220A/barnard"', 'name_col': 'Name'},
    'RCW':       {'table': '"VII/216/catalog"', 'name_col': 'Name'},
    'vdB':       {'table': '"VII/21/catalog"',  'name_col': 'Name'},
    'LDN':       {'table': '"VII/7A/catalog"',  'name_col': 'Name'},
    'Cederblad': {'table': '"VII/5/catalog"',   'name_col': 'Name'},
    'Abell':     {'table': '"VII/110A/table3"', 'name_col': 'Name'},
}

# Regex patterns for catalog prefix normalization
_CATALOG_PATTERNS = [
    # (regex, normalized_prefix, keep_separator)
    (re.compile(r'^M(?:ESSIER)?\s*(\d+)$', re.I),       'M',        ''),
    (re.compile(r'^NGC\s*0*(\d+[A-Z]?)$', re.I),        'NGC ',     ''),
    (re.compile(r'^IC\s*0*(\d+[A-Z]?)$', re.I),         'IC ',      ''),
    (re.compile(r'^C(?:ALDWELL)?\s*(\d+)$', re.I),       'Caldwell ',''),
    (re.compile(r'^SH\s*2?\s*[-_ ]?\s*(\d+)$', re.I),   'Sh2-',    ''),
    (re.compile(r'^ABELL\s*(\d+)$', re.I),               'Abell ',  ''),
    (re.compile(r'^ARP\s*(\d+)$', re.I),                 'Arp ',    ''),
    (re.compile(r'^B(?:ARNARD)?\s*(\d+)$', re.I),        'B ',      ''),
    (re.compile(r'^LBN\s*(\d+)$', re.I),                 'LBN ',    ''),
    (re.compile(r'^PGC\s*(\d+)$', re.I),                 'PGC ',    ''),
    (re.compile(r'^VDB\s*(\d+)$', re.I),                 'vdB ',    ''),
    (re.compile(r'^LDN\s*(\d+)$', re.I),                 'LDN ',    ''),
    (re.compile(r'^RCW\s*(\d+)$', re.I),                 'RCW ',    ''),
    (re.compile(r'^CED\s*(\d+[A-Z]?)$', re.I),           'Ced ',    ''),
]


class TargetResolver:
    """
    Enhanced multi-source astronomical target resolver.

    Resolution chain (first match wins):
      1. Local AstroManager database (targets table + simbad_data in observations)
      2. SIMBAD via astroquery (if installed)
      3. SESAME CDS XML service (NED + SIMBAD + VizieR)
      4. VizieR TAP queries (obscure catalogs)
    """

    def __init__(self):
        self.db = None
        self._init_db()

    def _init_db(self):
        """Lazy-initialize database connection."""
        try:
            from core.database import get_db
            self.db = get_db()
        except Exception as e:
            logger.warning(f"Database not available for target resolution: {e}")
            self.db = None

    # =========================================================================
    # PUBLIC: Main resolution entry point
    # =========================================================================

    def resolve(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Resolve an astronomical target name through the full resolution chain.

        Args:
            name: Target name (e.g. "M31", "NGC 7000", "Sh2-240")

        Returns:
            dict with keys: name, ra_deg, dec_deg, object_type, constellation,
            magnitude, size_arcmin, catalog_ids, aliases, description.
            Returns None if the target cannot be resolved by any source.
        """
        if not name or not name.strip():
            return None

        normalized = self.normalize_name(name.strip())
        logger.debug(f"Resolving target '{name}' (normalized: '{normalized}')")

        # Chain: local DB → SIMBAD → SESAME → VizieR TAP
        result = self.resolve_local(normalized)
        if result:
            logger.info(f"Target '{normalized}' resolved via local database")
            return result

        result = self.resolve_simbad(normalized)
        if result:
            logger.info(f"Target '{normalized}' resolved via SIMBAD")
            return result

        result = self.resolve_sesame(normalized)
        if result:
            logger.info(f"Target '{normalized}' resolved via SESAME")
            return result

        result = self.resolve_vizier_tap(normalized)
        if result:
            logger.info(f"Target '{normalized}' resolved via VizieR TAP")
            return result

        # Also try with the original (un-normalized) name if different
        if normalized != name.strip():
            result = self.resolve_sesame(name.strip())
            if result:
                logger.info(f"Target '{name}' resolved via SESAME (original name)")
                return result

        logger.warning(f"Target '{name}' could not be resolved by any source")
        return None

    # =========================================================================
    # LOCAL DATABASE RESOLUTION
    # =========================================================================

    def resolve_local(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Search the AstroManager local database for a target.

        Checks:
          - targets table (by name and canonical_name)
          - simbad_data JSON field in targets table

        Args:
            name: Normalized target name

        Returns:
            Standardized result dict or None
        """
        if self.db is None:
            return None

        try:
            # Search targets table by name or canonical_name
            target = self.db.get_target(name)
            if target:
                return self._target_row_to_result(target)

            # Search with variations (e.g. "M 31" vs "M31")
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Fuzzy match: strip spaces and compare
                cursor.execute(
                    "SELECT * FROM targets WHERE "
                    "REPLACE(UPPER(name), ' ', '') = REPLACE(UPPER(?), ' ', '') "
                    "OR REPLACE(UPPER(canonical_name), ' ', '') = REPLACE(UPPER(?), ' ', '')",
                    (name, name)
                )
                row = cursor.fetchone()
                if row:
                    return self._target_row_to_result(dict(row))

                # Search in simbad_data JSON field for aliases
                cursor.execute(
                    "SELECT * FROM targets WHERE simbad_data IS NOT NULL"
                )
                for row in cursor.fetchall():
                    row_dict = dict(row)
                    try:
                        simbad_data = json.loads(row_dict.get('simbad_data', '{}') or '{}')
                        aliases = simbad_data.get('aliases', [])
                        main_id = simbad_data.get('main_id', '')
                        # Check if our name matches any alias or main_id
                        name_upper = name.upper().replace(' ', '')
                        if main_id and main_id.upper().replace(' ', '') == name_upper:
                            return self._target_row_to_result(row_dict, simbad_data)
                        for alias in aliases:
                            if alias.upper().replace(' ', '') == name_upper:
                                return self._target_row_to_result(row_dict, simbad_data)
                    except (json.JSONDecodeError, TypeError):
                        continue

        except Exception as e:
            logger.warning(f"Local database search failed for '{name}': {e}")

        return None

    def _target_row_to_result(self, row: Dict, simbad_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Convert a database target row to a standardized result dict."""
        if simbad_data is None and row.get('simbad_data'):
            try:
                simbad_data = json.loads(row['simbad_data'])
            except (json.JSONDecodeError, TypeError):
                simbad_data = {}

        simbad_data = simbad_data or {}

        return {
            'name': row.get('canonical_name') or row.get('name', ''),
            'ra_deg': row.get('ra'),
            'dec_deg': row.get('dec'),
            'object_type': row.get('object_type') or simbad_data.get('object_type', ''),
            'constellation': simbad_data.get('constellation', ''),
            'magnitude': simbad_data.get('magnitude'),
            'size_arcmin': simbad_data.get('size_arcmin'),
            'catalog_ids': simbad_data.get('catalog_ids', []),
            'aliases': simbad_data.get('aliases', []),
            'description': simbad_data.get('description', ''),
            'source': 'local_database',
        }

    # =========================================================================
    # SIMBAD RESOLUTION (via astroquery — feature-gated)
    # =========================================================================

    def resolve_simbad(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Resolve target using SIMBAD via astroquery (if available).

        Queries: coordinates, object type, visual flux, dimensions.

        Args:
            name: Target name

        Returns:
            Standardized result dict or None
        """
        if not _HAS_ASTROQUERY:
            logger.debug("astroquery not available, skipping SIMBAD resolution")
            return None

        try:
            simbad = _AstroquerySimbad()
            simbad.TIMEOUT = SIMBAD_TIMEOUT

            # Request additional fields
            simbad.add_votable_fields('otype', 'ra(d)', 'dec(d)', 'flux(V)', 'dim')

            result = simbad.query_object(name)

            if result is None or len(result) == 0:
                return None

            row = result[0]

            ra_deg = float(row['RA_d']) if 'RA_d' in row.colnames else None
            dec_deg = float(row['DEC_d']) if 'DEC_d' in row.colnames else None
            object_type = str(row.get('OTYPE', '')).strip() if 'OTYPE' in row.colnames else ''
            main_id = str(row.get('MAIN_ID', name)).strip()

            # Visual magnitude
            magnitude = None
            if 'FLUX_V' in row.colnames:
                try:
                    mag_val = row['FLUX_V']
                    if mag_val is not None and str(mag_val).strip() not in ('', '--'):
                        magnitude = float(mag_val)
                except (ValueError, TypeError):
                    pass

            # Angular dimensions (major axis in arcmin)
            size_arcmin = None
            if 'GALDIM_MAJAXIS' in row.colnames:
                try:
                    dim_val = row['GALDIM_MAJAXIS']
                    if dim_val is not None and str(dim_val).strip() not in ('', '--'):
                        size_arcmin = float(dim_val)
                except (ValueError, TypeError):
                    pass

            # Get aliases / identifiers
            aliases = []
            catalog_ids = []
            try:
                ids_result = simbad.query_objectids(name)
                if ids_result:
                    for r in ids_result:
                        ident = str(r['ID']).strip()
                        aliases.append(ident)
                        # Extract catalog IDs (M, NGC, IC, etc.)
                        normalized_id = self.normalize_name(ident)
                        if normalized_id and normalized_id != ident:
                            catalog_ids.append(normalized_id)
                        elif ident:
                            catalog_ids.append(ident)
            except Exception:
                pass

            # Sort catalog IDs by priority
            catalog_ids = sorted(set(catalog_ids),
                                 key=lambda x: self.get_catalog_priority(x))

            return {
                'name': main_id,
                'ra_deg': ra_deg,
                'dec_deg': dec_deg,
                'object_type': object_type,
                'constellation': '',  # SIMBAD otype doesn't directly give constellation
                'magnitude': magnitude,
                'size_arcmin': size_arcmin,
                'catalog_ids': catalog_ids,
                'aliases': aliases,
                'description': '',
                'source': 'simbad',
            }

        except ImportError:
            logger.debug("astroquery import failed at runtime")
            return None
        except Exception as e:
            logger.debug(f"SIMBAD query failed for '{name}': {e}")
            return None

    # =========================================================================
    # SESAME RESOLUTION (CDS XML service — stdlib HTTP)
    # =========================================================================

    def resolve_sesame(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Resolve target using SESAME CDS multi-resolver (NED + SIMBAD + VizieR).

        HTTP GET to CDS endpoint, parses XML response for coordinates,
        object type, and aliases.

        Args:
            name: Target name

        Returns:
            Standardized result dict or None
        """
        import urllib.request
        import urllib.error

        try:
            # URL-encode the target name for safe HTTP request
            encoded_name = quote_plus(name)
            url = f"{SESAME_URL}?{encoded_name}"

            req = urllib.request.Request(url)
            req.add_header('User-Agent', USER_AGENT)

            with urllib.request.urlopen(req, timeout=SESAME_TIMEOUT) as response:
                if response.status != 200:
                    logger.debug(f"SESAME returned HTTP {response.status} for '{name}'")
                    return None

                raw_data = response.read(1_048_576)  # 1 MB limit

            # Parse XML response
            xml_text = raw_data.decode('utf-8', errors='replace')
            if not xml_text.strip():
                return None

            return self._parse_sesame_xml(xml_text, name)

        except urllib.error.URLError as e:
            logger.debug(f"SESAME connection error for '{name}': {e}")
            return None
        except Exception as e:
            logger.debug(f"SESAME resolution failed for '{name}': {e}")
            return None

    def _parse_sesame_xml(self, xml_text: str, original_name: str) -> Optional[Dict[str, Any]]:
        """
        Parse SESAME XML response and extract target metadata.

        SESAME XML structure:
          <Sesame> <Target> <Resolver name="S=Simbad">
            <jpos>hh mm ss.s +dd mm ss</jpos>
            <jradeg>ra_degrees</jradeg>
            <jdedeg>dec_degrees</jdedeg>
            <oname>object name</oname>
            <otype>object type</otype>
            <alias>...</alias>
          </Resolver> </Target> </Sesame>
        """
        try:
            root = _xml_fromstring(xml_text)
        except ET.ParseError as e:
            logger.debug(f"SESAME XML parse error: {e}")
            return None

        # Find the first successful resolver (Simbad, NED, or VizieR)
        target = root.find('.//Target')
        if target is None:
            return None

        ra_deg = None
        dec_deg = None
        object_type = ''
        object_name = original_name
        aliases = []
        description = ''

        # Try each resolver block (Simbad first, then NED, then VizieR)
        for resolver in target.findall('Resolver'):
            # Check if this resolver returned valid data
            jradeg_elem = resolver.find('jradeg')
            jdedeg_elem = resolver.find('jdedeg')

            if jradeg_elem is not None and jdedeg_elem is not None:
                try:
                    ra_deg = float(jradeg_elem.text.strip())
                    dec_deg = float(jdedeg_elem.text.strip())
                except (ValueError, TypeError, AttributeError):
                    continue

                # Object name
                oname_elem = resolver.find('oname')
                if oname_elem is not None and oname_elem.text:
                    object_name = oname_elem.text.strip()

                # Object type
                otype_elem = resolver.find('otype')
                if otype_elem is not None and otype_elem.text:
                    object_type = otype_elem.text.strip()

                # Aliases
                for alias_elem in resolver.findall('alias'):
                    if alias_elem.text and alias_elem.text.strip():
                        aliases.append(alias_elem.text.strip())

                # Description (if available)
                desc_elem = resolver.find('description')
                if desc_elem is not None and desc_elem.text:
                    description = desc_elem.text.strip()

                break  # Use first resolver that returns coordinates

        if ra_deg is None or dec_deg is None:
            return None

        # Validate coordinate ranges
        if not (-360.0 <= ra_deg <= 360.0) or not (-90.0 <= dec_deg <= 90.0):
            logger.debug(f"SESAME returned invalid coordinates: RA={ra_deg}, Dec={dec_deg}")
            return None

        # Normalize RA to [0, 360)
        ra_deg = ra_deg % 360.0

        # Extract catalog IDs from aliases
        catalog_ids = []
        for alias in aliases:
            normalized = self.normalize_name(alias)
            if normalized:
                catalog_ids.append(normalized)

        catalog_ids = sorted(set(catalog_ids),
                             key=lambda x: self.get_catalog_priority(x))

        return {
            'name': object_name,
            'ra_deg': ra_deg,
            'dec_deg': dec_deg,
            'object_type': object_type,
            'constellation': '',
            'magnitude': None,
            'size_arcmin': None,
            'catalog_ids': catalog_ids,
            'aliases': aliases,
            'description': description,
            'source': 'sesame',
        }

    # =========================================================================
    # VIZIER TAP RESOLUTION (obscure catalogs)
    # =========================================================================

    def resolve_vizier_tap(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Resolve target using VizieR TAP sync queries against obscure catalogs
        (Sharpless, LBN, Barnard dark nebulae, RCW, vdB, LDN, Cederblad, Abell).

        Uses ADQL queries via the TAP sync endpoint, parses VOTable response.

        Args:
            name: Target name

        Returns:
            Standardized result dict or None
        """
        import urllib.request
        import urllib.error

        # Determine which VizieR catalog(s) to search based on name prefix
        catalogs_to_search = self._select_vizier_catalogs(name)

        if not catalogs_to_search:
            # If no specific catalog identified, search all
            catalogs_to_search = list(VIZIER_CATALOGS.keys())

        for catalog_name in catalogs_to_search:
            cat_info = VIZIER_CATALOGS.get(catalog_name)
            if not cat_info:
                continue

            result = self._query_vizier_catalog(name, cat_info, catalog_name)
            if result:
                return result

        return None

    def _select_vizier_catalogs(self, name: str) -> List[str]:
        """Determine which VizieR catalogs to search based on the target name prefix."""
        name_upper = name.upper().strip()

        mapping = {
            'SH2': ['Sharpless'],
            'SH': ['Sharpless'],
            'LBN': ['LBN'],
            'B': ['Barnard'],
            'BARNARD': ['Barnard'],
            'RCW': ['RCW'],
            'VDB': ['vdB'],
            'LDN': ['LDN'],
            'CED': ['Cederblad'],
            'ABELL': ['Abell'],
        }

        for prefix, catalogs in mapping.items():
            if name_upper.startswith(prefix):
                # Verify that what follows the prefix is a number or separator+number
                remainder = name_upper[len(prefix):]
                if not remainder or re.match(r'^[\s\-_]*\d', remainder):
                    return catalogs

        return []

    def _query_vizier_catalog(self, name: str, cat_info: Dict,
                              catalog_name: str) -> Optional[Dict[str, Any]]:
        """Execute a single VizieR TAP query for one catalog."""
        import urllib.request
        import urllib.error

        try:
            # Sanitize the name for ADQL LIKE clause:
            # Escape ADQL special chars (%, _, single quote)
            safe_name = name.replace("'", "''")
            safe_name = safe_name.replace('%', r'\%')
            safe_name = safe_name.replace('_', r'\_')
            # Reject ADQL injection characters
            safe_name = safe_name.replace('--', '').replace(';', '').replace('\n', ' ').replace('\r', ' ')

            # Also try a numeric-only form (e.g. "Sh2-240" → "240")
            num_match = re.search(r'(\d+)', name)
            numeric_part = num_match.group(1) if num_match else ''
            # Strip non-numeric characters to prevent ADQL injection
            numeric_part = ''.join(c for c in numeric_part if c.isdigit() or c == '.')

            # ADQL query — search by name LIKE
            table = cat_info['table']
            name_col = cat_info['name_col']

            adql = (
                f"SELECT TOP 5 * FROM {table} "
                f"WHERE {name_col} LIKE '%{safe_name}%'"
            )

            params = urlencode({
                'REQUEST': 'doQuery',
                'LANG': 'ADQL',
                'FORMAT': 'votable',
                'QUERY': adql,
            })

            req = urllib.request.Request(
                VIZIER_TAP_URL,
                data=params.encode('utf-8'),
                method='POST'
            )
            req.add_header('User-Agent', USER_AGENT)
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')

            with urllib.request.urlopen(req, timeout=VIZIER_TIMEOUT) as response:
                if response.status != 200:
                    return None
                raw_data = response.read(1_048_576)  # 1 MB limit

            result = self._parse_votable(raw_data, name, catalog_name)
            if result:
                return result

            # If no match with full name, try with numeric part only
            if numeric_part and numeric_part != safe_name:
                adql_num = (
                    f"SELECT TOP 5 * FROM {table} "
                    f"WHERE {name_col} LIKE '%{numeric_part}%'"
                )

                params_num = urlencode({
                    'REQUEST': 'doQuery',
                    'LANG': 'ADQL',
                    'FORMAT': 'votable',
                    'QUERY': adql_num,
                })

                req_num = urllib.request.Request(
                    VIZIER_TAP_URL,
                    data=params_num.encode('utf-8'),
                    method='POST'
                )
                req_num.add_header('User-Agent', USER_AGENT)
                req_num.add_header('Content-Type', 'application/x-www-form-urlencoded')

                with urllib.request.urlopen(req_num, timeout=VIZIER_TIMEOUT) as resp:
                    if resp.status != 200:
                        return None
                    raw_data_num = resp.read(1_048_576)  # 1 MB limit

                return self._parse_votable(raw_data_num, name, catalog_name)

        except urllib.error.URLError as e:
            logger.debug(f"VizieR TAP connection error for '{name}' ({catalog_name}): {e}")
        except Exception as e:
            logger.debug(f"VizieR TAP query failed for '{name}' ({catalog_name}): {e}")

        return None

    def _parse_votable(self, raw_data: bytes, original_name: str,
                       catalog_name: str) -> Optional[Dict[str, Any]]:
        """
        Parse VOTable XML response from VizieR TAP.

        Extracts RA/Dec from standard column names (_RAJ2000/_DEJ2000 or RAJ2000/DEJ2000).
        """
        try:
            xml_text = raw_data.decode('utf-8', errors='replace')
            if not xml_text.strip():
                return None

            root = _xml_fromstring(xml_text)
        except ET.ParseError as e:
            logger.debug(f"VOTable parse error: {e}")
            return None

        # VOTable namespace
        ns = {'v': 'http://www.ivoa.net/xml/VOTable/v1.3'}
        # Try without namespace too (some responses vary)
        ns_alt = {'v': 'http://www.ivoa.net/xml/VOTable/v1.2'}

        for namespace in [ns, ns_alt, {}]:
            rows = self._extract_votable_rows(root, namespace)
            if rows:
                break
        else:
            return None

        if not rows:
            return None

        # Use first row
        row = rows[0]

        ra_deg = None
        dec_deg = None

        # Try common RA/Dec column names
        for ra_key in ['_RAJ2000', 'RAJ2000', 'RA', 'GLON', 'ra']:
            if ra_key in row and row[ra_key] is not None:
                try:
                    ra_deg = float(row[ra_key])
                    break
                except (ValueError, TypeError):
                    pass

        for dec_key in ['_DEJ2000', 'DEJ2000', 'DEC', 'GLAT', 'dec']:
            if dec_key in row and row[dec_key] is not None:
                try:
                    dec_deg = float(row[dec_key])
                    break
                except (ValueError, TypeError):
                    pass

        if ra_deg is None or dec_deg is None:
            return None

        # Validate coordinates
        if not (-360.0 <= ra_deg <= 360.0) or not (-90.0 <= dec_deg <= 90.0):
            return None

        ra_deg = ra_deg % 360.0

        # Extract additional fields if available
        object_name = row.get('Name', row.get('name', original_name))
        if object_name:
            object_name = str(object_name).strip()

        return {
            'name': object_name or original_name,
            'ra_deg': ra_deg,
            'dec_deg': dec_deg,
            'object_type': catalog_name,
            'constellation': '',
            'magnitude': None,
            'size_arcmin': None,
            'catalog_ids': [original_name],
            'aliases': [],
            'description': f"From VizieR catalog {catalog_name}",
            'source': 'vizier_tap',
        }

    def _extract_votable_rows(self, root, namespace: Dict) -> List[Dict[str, str]]:
        """Extract data rows from a VOTable XML element tree."""
        prefix = 'v:' if namespace else ''

        # Find FIELD definitions (column names)
        fields = root.findall(f'.//{prefix}FIELD', namespace) if namespace else root.findall('.//FIELD')
        if not fields:
            # Try alternative paths
            fields = root.findall(f'.//{prefix}TABLE/{prefix}FIELD', namespace) if namespace else []

        col_names = []
        for f in fields:
            col_names.append(f.get('name', f'col{len(col_names)}'))

        # Find TABLEDATA rows
        tabledata = root.find(f'.//{prefix}TABLEDATA', namespace) if namespace else root.find('.//TABLEDATA')
        if tabledata is None:
            return []

        rows = []
        for tr in (tabledata.findall(f'{prefix}TR', namespace) if namespace
                   else tabledata.findall('TR')):
            tds = (tr.findall(f'{prefix}TD', namespace) if namespace
                   else tr.findall('TD'))
            row_data = {}
            for i, td in enumerate(tds):
                col_name = col_names[i] if i < len(col_names) else f'col{i}'
                row_data[col_name] = td.text.strip() if td.text else None
            if row_data:
                rows.append(row_data)

        return rows

    # =========================================================================
    # NAME NORMALIZATION
    # =========================================================================

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Normalize an astronomical target name to a canonical form.

        Examples:
            "M 31"    → "M31"
            "NGC0224" → "NGC 224"
            "IC0001"  → "IC 1"
            "Sh2 240" → "Sh2-240"
            "  m  42" → "M42"

        Args:
            name: Raw target name

        Returns:
            Normalized name string
        """
        if not name:
            return ''

        cleaned = name.strip()
        if not cleaned:
            return ''

        for pattern, prefix, _sep in _CATALOG_PATTERNS:
            match = pattern.match(cleaned)
            if match:
                number = match.group(1)
                # Strip leading zeros but keep at least one digit
                if number.isdigit():
                    number = str(int(number))
                elif number[:-1].isdigit() and number[-1].isalpha():
                    # e.g. "224A" → strip zeros from numeric part
                    number = str(int(number[:-1])) + number[-1]
                return f"{prefix}{number}"

        # No catalog pattern matched — return cleaned version
        return cleaned

    # =========================================================================
    # CATALOG PRIORITY
    # =========================================================================

    @staticmethod
    def get_catalog_priority(name: str) -> int:
        """
        Return a priority value for a catalog name (lower = higher priority).

        Used for sorting when multiple catalog IDs are found.

        Priority: M(1) > NGC(2) > IC(3) > Caldwell(4) > Sh2(5) > Abell(6)
                  > Arp(7) > Barnard(8) > LBN(9) > PGC(10) > vdB(11)
                  > LDN(12) > RCW(13) > Ced(14)

        Args:
            name: Catalog identifier string

        Returns:
            Priority integer (lower = higher priority), 99 for unknown
        """
        if not name:
            return 99

        name_upper = name.upper().strip()

        # Check known prefixes
        for prefix, priority in CATALOG_PRIORITY.items():
            if name_upper.startswith(prefix):
                # Verify it's actually a catalog ID (followed by space/digit/dash)
                remainder = name_upper[len(prefix):]
                if not remainder or re.match(r'^[\s\-_]*\d', remainder):
                    return priority

        return 99

    # =========================================================================
    # COORDINATE HELPERS
    # =========================================================================

    @staticmethod
    def sexagesimal_to_degrees(ra_sex: str, dec_sex: str) -> Optional[tuple]:
        """
        Convert sexagesimal coordinates to decimal degrees.

        Args:
            ra_sex: RA string like "05 34 31.97" or "05h34m31.97s"
            dec_sex: Dec string like "+22 00 52.1" or "+22d00m52.1s"

        Returns:
            (ra_deg, dec_deg) tuple or None on parse error
        """
        try:
            # Clean RA: remove h/m/s, replace with spaces
            ra_clean = re.sub(r'[hms]', ' ', ra_sex).strip()
            parts = ra_clean.split()
            if len(parts) < 2:
                return None

            ra_h = float(parts[0])
            ra_m = float(parts[1]) if len(parts) > 1 else 0.0
            ra_s = float(parts[2]) if len(parts) > 2 else 0.0
            ra_deg = (ra_h + ra_m / 60.0 + ra_s / 3600.0) * 15.0

            # Clean Dec: remove d/m/s/°/'/", replace with spaces
            dec_clean = re.sub(r'[dms°\'"]', ' ', dec_sex).strip()
            # Handle sign
            dec_sign = 1.0
            if dec_clean.startswith('-'):
                dec_sign = -1.0
                dec_clean = dec_clean[1:].strip()
            elif dec_clean.startswith('+'):
                dec_clean = dec_clean[1:].strip()

            parts = dec_clean.split()
            if len(parts) < 1:
                return None

            dec_d = float(parts[0])
            dec_m = float(parts[1]) if len(parts) > 1 else 0.0
            dec_s = float(parts[2]) if len(parts) > 2 else 0.0
            dec_deg = dec_sign * (dec_d + dec_m / 60.0 + dec_s / 3600.0)

            # Validate
            if not (0.0 <= ra_deg < 360.0) or not (-90.0 <= dec_deg <= 90.0):
                return None

            return (ra_deg, dec_deg)

        except (ValueError, TypeError, IndexError):
            return None

    @staticmethod
    def degrees_to_sexagesimal(ra_deg: float, dec_deg: float) -> Optional[tuple]:
        """
        Convert decimal degrees to sexagesimal strings.

        Args:
            ra_deg: Right Ascension in degrees [0, 360)
            dec_deg: Declination in degrees [-90, +90]

        Returns:
            (ra_str, dec_str) tuple like ("05h 34m 31.97s", "+22d 00m 52.1s")
            or None on invalid input
        """
        try:
            if not (0.0 <= ra_deg < 360.0) or not (-90.0 <= dec_deg <= 90.0):
                return None

            # RA: degrees → hours
            ra_hours_total = ra_deg / 15.0
            ra_h = int(ra_hours_total)
            ra_m = int((ra_hours_total - ra_h) * 60)
            ra_s = (ra_hours_total - ra_h - ra_m / 60.0) * 3600.0
            ra_str = f"{ra_h:02d}h {ra_m:02d}m {ra_s:05.2f}s"

            # Dec: degrees → dms
            dec_sign = '+' if dec_deg >= 0 else '-'
            dec_abs = abs(dec_deg)
            dec_d = int(dec_abs)
            dec_m = int((dec_abs - dec_d) * 60)
            dec_s = (dec_abs - dec_d - dec_m / 60.0) * 3600.0
            dec_str = f"{dec_sign}{dec_d:02d}d {dec_m:02d}m {dec_s:04.1f}s"

            return (ra_str, dec_str)

        except (ValueError, TypeError):
            return None
