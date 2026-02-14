#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
COMPRESSION ENGINE - Universal FITS/XISF/FZ Converter
================================================================================
Supports all compression formats and conversions:
- FITS ↔ XISF (zlib, zstd, lz4 at all levels)
- FITS ↔ FITS.FZ (fpack/funpack via astropy)
- XISF ↔ FITS.FZ
- All combinations, fully PixInsight compatible
================================================================================
"""

import os
import sys
import struct
import zlib
import hashlib
import numpy as np
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

try:
    from astropy.io import fits as astropy_fits
    ASTROPY_AVAILABLE = True
except ImportError:
    ASTROPY_AVAILABLE = False

try:
    import lz4.block
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False

try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

try:
    from xisf import XISF
    HAS_XISF_LIB = True
except ImportError:
    HAS_XISF_LIB = False


# ============================================================================
# COMPRESSION PROFILES - User-selectable with explanations
# ============================================================================

COMPRESSION_PROFILES = {
    'zlib_6': {
        'codec': 'zlib',
        'level': 6,
        'shuffle': True,
        'name_en': 'zlib Level 6 (Recommended)',
        'name_fr': 'zlib Niveau 6 (Recommandé)',
        'desc_en': 'Best balance between compression ratio and speed. '
                   'Compatible with all XISF readers including PixInsight. '
                   'Typically 40-60% compression on astronomical images.',
        'desc_fr': 'Meilleur équilibre entre taux de compression et vitesse. '
                   'Compatible avec tous les lecteurs XISF dont PixInsight. '
                   'Typiquement 40-60% de compression sur les images astronomiques.',
    },
    'zlib_1': {
        'codec': 'zlib',
        'level': 1,
        'shuffle': True,
        'name_en': 'zlib Level 1 (Fastest)',
        'name_fr': 'zlib Niveau 1 (Plus rapide)',
        'desc_en': 'Fastest compression with decent ratio. '
                   'Good for quick archiving when speed matters more than size.',
        'desc_fr': 'Compression la plus rapide avec un taux correct. '
                   'Idéal pour un archivage rapide quand la vitesse prime.',
    },
    'zlib_9': {
        'codec': 'zlib',
        'level': 9,
        'shuffle': True,
        'name_en': 'zlib Level 9 (Maximum)',
        'name_fr': 'zlib Niveau 9 (Maximum)',
        'desc_en': 'Maximum zlib compression. Slower but smallest files. '
                   'Only 2-5% smaller than level 6, much slower.',
        'desc_fr': 'Compression zlib maximale. Plus lent mais fichiers plus petits. '
                   'Seulement 2-5% plus petit que le niveau 6, bien plus lent.',
    },
    'zstd_3': {
        'codec': 'zstd',
        'level': 3,
        'shuffle': True,
        'name_en': 'Zstandard Level 3 (Fast)',
        'name_fr': 'Zstandard Niveau 3 (Rapide)',
        'desc_en': 'Modern codec, faster than zlib with similar ratio. '
                   'Requires zstandard package. PixInsight compatible.',
        'desc_fr': 'Codec moderne, plus rapide que zlib pour un taux similaire. '
                   'Nécessite le package zstandard. Compatible PixInsight.',
    },
    'zstd_6': {
        'codec': 'zstd',
        'level': 6,
        'shuffle': True,
        'name_en': 'Zstandard Level 6 (Balanced)',
        'name_fr': 'Zstandard Niveau 6 (Équilibré)',
        'desc_en': 'Good balance for Zstandard. Better compression than zlib-6 '
                   'at comparable speed.',
        'desc_fr': 'Bon équilibre pour Zstandard. Meilleure compression que zlib-6 '
                   'à vitesse comparable.',
    },
    'zstd_10': {
        'codec': 'zstd',
        'level': 10,
        'shuffle': True,
        'name_en': 'Zstandard Level 10 (High)',
        'name_fr': 'Zstandard Niveau 10 (Élevé)',
        'desc_en': 'High compression with Zstandard. Noticeably slower '
                   'but excellent compression ratio.',
        'desc_fr': 'Haute compression avec Zstandard. Notablement plus lent '
                   'mais excellent taux de compression.',
    },
    'zstd_19': {
        'codec': 'zstd',
        'level': 19,
        'shuffle': True,
        'name_en': 'Zstandard Level 19 (Maximum)',
        'name_fr': 'Zstandard Niveau 19 (Maximum)',
        'desc_en': 'Maximum Zstandard compression. Very slow but smallest files. '
                   'Best for long-term archival of data you rarely access.',
        'desc_fr': 'Compression Zstandard maximale. Très lent mais fichiers les plus petits. '
                   'Idéal pour l\'archivage à long terme de données rarement accédées.',
    },
    'lz4': {
        'codec': 'lz4',
        'level': 0,
        'shuffle': True,
        'name_en': 'LZ4 (Ultra-Fast)',
        'name_fr': 'LZ4 (Ultra-rapide)',
        'desc_en': 'Extremely fast compression and decompression. '
                   'Lower ratio than zlib/zstd but 5-10x faster. '
                   'Best when I/O speed is critical.',
        'desc_fr': 'Compression et décompression extrêmement rapides. '
                   'Taux plus bas que zlib/zstd mais 5-10x plus rapide. '
                   'Idéal quand la vitesse d\'E/S est critique.',
    },
    'lz4_hc': {
        'codec': 'lz4_hc',
        'level': 9,
        'shuffle': True,
        'name_en': 'LZ4 HC (High Compression)',
        'name_fr': 'LZ4 HC (Haute Compression)',
        'desc_en': 'LZ4 High Compression mode. Better ratio than standard LZ4, '
                   'still faster decompression than zlib.',
        'desc_fr': 'Mode LZ4 Haute Compression. Meilleur taux que le LZ4 standard, '
                   'décompression toujours plus rapide que zlib.',
    },
    'none': {
        'codec': 'none',
        'level': 0,
        'shuffle': False,
        'name_en': 'No Compression (Raw XISF)',
        'name_fr': 'Sans Compression (XISF brut)',
        'desc_en': 'No compression applied. Fastest read/write but large files. '
                   'Useful for temporary working files.',
        'desc_fr': 'Aucune compression appliquée. Lecture/écriture la plus rapide. '
                   'Utile pour les fichiers de travail temporaires.',
    },
}


def get_available_profiles():
    """Return only profiles whose codec is available on this system."""
    available = {}
    for key, profile in COMPRESSION_PROFILES.items():
        codec = profile['codec']
        if codec == 'zlib' or codec == 'none':
            available[key] = profile
        elif codec in ('zstd',) and HAS_ZSTD:
            available[key] = profile
        elif codec in ('lz4', 'lz4_hc') and HAS_LZ4:
            available[key] = profile
    return available


# ============================================================================
# BYTE SHUFFLING (PixInsight compatible)
# ============================================================================

def byte_shuffle(data: bytes, item_size: int) -> bytes:
    """Apply byte shuffling for better compression (XISF spec)."""
    arr = np.frombuffer(data, dtype=np.uint8)
    n_items = len(arr) // item_size
    if n_items * item_size != len(arr):
        return data
    reshaped = arr[:n_items * item_size].reshape(n_items, item_size)
    shuffled = reshaped.T.ravel()
    remainder = arr[n_items * item_size:]
    if len(remainder) > 0:
        shuffled = np.concatenate([shuffled, remainder])
    return shuffled.tobytes()


def byte_unshuffle(data: bytes, item_size: int) -> bytes:
    """Reverse byte shuffling."""
    arr = np.frombuffer(data, dtype=np.uint8)
    n_items = len(arr) // item_size
    if n_items * item_size != len(arr):
        return data
    reshaped = arr[:n_items * item_size].reshape(item_size, n_items)
    unshuffled = reshaped.T.ravel()
    remainder = arr[n_items * item_size:]
    if len(remainder) > 0:
        unshuffled = np.concatenate([unshuffled, remainder])
    return unshuffled.tobytes()


# ============================================================================
# COMPRESS / DECOMPRESS FUNCTIONS
# ============================================================================

def compress_data(data: bytes, codec: str, level: int = 6,
                  shuffle: bool = True, item_size: int = 2) -> bytes:
    """Compress raw bytes with the specified codec."""
    work = data
    if shuffle and item_size > 1:
        work = byte_shuffle(work, item_size)

    if codec == 'zlib':
        return zlib.compress(work, level=level)
    elif codec in ('zstd',):
        if not HAS_ZSTD:
            raise RuntimeError("zstandard package not installed (pip install zstandard)")
        cctx = zstd.ZstdCompressor(level=level)
        return cctx.compress(work)
    elif codec == 'lz4':
        if not HAS_LZ4:
            raise RuntimeError("lz4 package not installed (pip install lz4)")
        return lz4.block.compress(work, store_size=False)
    elif codec == 'lz4_hc':
        if not HAS_LZ4:
            raise RuntimeError("lz4 package not installed (pip install lz4)")
        return lz4.block.compress(work, mode='high_compression',
                                  compression=level, store_size=False)
    elif codec == 'none':
        return work
    else:
        raise ValueError(f"Unknown codec: {codec}")


def decompress_data(data: bytes, codec: str, original_size: int,
                    shuffle: bool = False, item_size: int = 2) -> bytes:
    """Decompress bytes with the specified codec."""
    if codec == 'zlib':
        raw = zlib.decompress(data)
    elif codec in ('zstd',):
        if not HAS_ZSTD:
            raise RuntimeError("zstandard package not installed")
        dctx = zstd.ZstdDecompressor()
        raw = dctx.decompress(data, max_output_size=original_size)
    elif codec in ('lz4', 'lz4_hc'):
        if not HAS_LZ4:
            raise RuntimeError("lz4 package not installed")
        raw = lz4.block.decompress(data, uncompressed_size=original_size)
    elif codec == 'none':
        raw = data
    else:
        raise ValueError(f"Unknown codec: {codec}")

    if shuffle and item_size > 1:
        raw = byte_unshuffle(raw, item_size)
    return raw


# ============================================================================
# XISF WRITER - Enhanced, supports all codecs (PixInsight compatible)
# ============================================================================

class XISFWriter:
    """Write XISF files with any supported compression codec."""

    _BLOCK_ALIGNMENT = 4096

    def __init__(self, filepath, codec='zlib', level=6, shuffle=True):
        self.filepath = str(filepath)
        self.codec = codec
        self.level = level
        self.shuffle = shuffle

    def write_image(self, data: np.ndarray, header=None):
        """Write image data and optional FITS header to XISF."""
        if not data.flags['C_CONTIGUOUS']:
            data = np.ascontiguousarray(data)
        if data.dtype.byteorder == '>':
            data = data.byteswap().newbyteorder()

        image_bytes = data.tobytes()
        original_size = len(image_bytes)
        item_size = data.dtype.itemsize

        compressed = compress_data(image_bytes, self.codec, self.level,
                                   self.shuffle, item_size)
        compressed_size = len(compressed)

        def _aligned(pos, align=self._BLOCK_ALIGNMENT):
            return ((pos + align - 1) // align) * align

        offset = 0
        for _ in range(5):
            xml_str = self._build_xml(data, compressed_size, original_size,
                                      header, offset)
            xml_bytes = xml_str.encode('utf-8')
            header_total = 8 + 4 + 4 + len(xml_bytes)
            new_offset = _aligned(header_total)
            if new_offset == offset:
                break
            offset = new_offset

        xml_str = self._build_xml(data, compressed_size, original_size,
                                  header, offset)
        xml_bytes = xml_str.encode('utf-8')
        header_total = 8 + 4 + 4 + len(xml_bytes)
        padding = _aligned(header_total) - header_total

        with open(self.filepath, 'wb') as f:
            f.write(b'XISF0100')
            f.write(struct.pack('<I', len(xml_bytes)))
            f.write(b'\x00\x00\x00\x00')
            f.write(xml_bytes)
            if padding > 0:
                f.write(b'\x00' * padding)
            f.write(compressed)

        return {
            'original_size': original_size,
            'compressed_size': compressed_size,
            'ratio': (1 - compressed_size / original_size) * 100 if original_size > 0 else 0,
        }

    @staticmethod
    def _escape_xml(s):
        """Escape XML special characters."""
        return (str(s).replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;').replace('"', '&quot;')
                .replace("'", '&apos;'))

    def _build_xml(self, data, compressed_size, original_size, fits_header, data_offset):
        """Build XISF XML header."""
        # Geometry
        if len(data.shape) == 2:
            geometry = f"{data.shape[1]}:{data.shape[0]}:1"
        elif len(data.shape) == 3:
            geometry = f"{data.shape[2]}:{data.shape[1]}:{data.shape[0]}"
        else:
            geometry = f"{data.shape[-1]}:{data.shape[-2]}:1"

        dtype_map = {
            'uint8': 'UInt8', 'uint16': 'UInt16', 'uint32': 'UInt32',
            'int16': 'Int16', 'int32': 'Int32',
            'float32': 'Float32', 'float64': 'Float64',
        }
        sample_format = dtype_map.get(data.dtype.name, 'Float32')
        color_space = "RGB" if (len(data.shape) == 3 and data.shape[0] == 3) else "Gray"

        # Compression attribute (XISF 1.0 spec)
        codec_attr = ''
        if self.codec != 'none':
            algo = self.codec.replace('_hc', '-hc')
            if self.shuffle:
                algo += '+sh'
            if self.shuffle:
                codec_attr = f'{algo}:{original_size}:{data.dtype.itemsize}'
            else:
                codec_attr = f'{algo}:{original_size}'

        location = f'attachment:{int(data_offset)}:{int(compressed_size)}'

        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<xisf version="1.0" xmlns="http://www.pixinsight.com/xisf" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:schemaLocation="http://www.pixinsight.com/xisf '
            'http://pixinsight.com/xisf/xisf-1.0.xsd">',
        ]

        img_attrs = [
            f'geometry="{geometry}"',
            f'sampleFormat="{sample_format}"',
            f'colorSpace="{color_space}"',
            f'location="{location}"',
        ]
        if sample_format in ('Float32', 'Float64'):
            img_attrs.insert(2, 'bounds="0:1"')
        if codec_attr:
            img_attrs.append(f'compression="{codec_attr}"')

        parts.append('  <Image ' + ' '.join(img_attrs) + '>')

        # FITS keywords
        if fits_header:
            for card in fits_header.cards:
                keyword = str(card.keyword).strip()
                if not keyword:
                    continue
                value = self._escape_xml(str(card.value))
                comment = self._escape_xml(str(card.comment)) if card.comment else ""
                line = f'    <FITSKeyword name="{keyword}" value="{value}"'
                if comment:
                    line += f' comment="{comment}"'
                line += ' />'
                parts.append(line)

        parts.append('  </Image>')

        # Metadata
        parts.append('  <Metadata>')
        parts.append(f'    <Property id="XISF:CreationTime" type="String" '
                     f'value="{datetime.utcnow().isoformat()}"/>')
        parts.append('    <Property id="XISF:CreatorApplication" type="String" '
                     'value="AstroFileManager"/>')
        codec_desc = f"{self.codec} level={self.level}" if self.codec != 'none' else 'none'
        parts.append(f'    <Property id="XISF:CompressionCodec" type="String" '
                     f'value="{codec_desc}"/>')
        parts.append('  </Metadata>')
        parts.append('</xisf>')

        return '\n'.join(parts)


# ============================================================================
# XISF READER - Enhanced, supports all codecs
# ============================================================================

class XISFReader:
    """Read XISF files with any compression codec."""

    def __init__(self, filepath):
        self.filepath = str(filepath)

    def read_image(self):
        """Read image data and metadata from XISF.
        Returns (np.ndarray, dict_metadata) or raises on error.
        """
        # Try xisf library first (most reliable)
        if HAS_XISF_LIB:
            try:
                return self._read_with_library()
            except Exception:
                pass

        # Fallback: manual reader
        return self._read_manual()

    def read_header_only(self):
        """Read only the metadata/header without loading image data."""
        try:
            with open(self.filepath, 'rb') as f:
                sig = f.read(8)
                if sig != b'XISF0100':
                    return {}
                header_length = struct.unpack('<I', f.read(4))[0]
                f.read(4)  # reserved
                xml_bytes = f.read(header_length)

            xml_string = xml_bytes.rstrip(b'\x00').decode('utf-8')
            if xml_string.startswith('<?xml'):
                xml_string = xml_string[xml_string.index('?>') + 2:].strip()

            root = ET.fromstring(xml_string)
            ns = {'xisf': 'http://www.pixinsight.com/xisf'}
            image = root.find('xisf:Image', ns) or root.find('Image')
            if image is None:
                return {}

            header_dict = {}
            for kw in (image.findall('xisf:FITSKeyword', ns) or
                       image.findall('FITSKeyword')):
                name = kw.get('name', '')
                val = kw.get('value', '')
                val = self._parse_fits_value(val)
                header_dict[name] = val
            return header_dict

        except Exception:
            return {}

    def _read_with_library(self):
        """Read using the xisf Python library."""
        xisf_obj = XISF(self.filepath)
        meta = xisf_obj.get_images_metadata()
        if not meta:
            raise ValueError("No image metadata found")

        im = xisf_obj.read_image(0)
        if len(im.shape) == 3 and im.shape[2] == 1:
            im = im[:, :, 0]
        elif len(im.shape) == 3 and im.shape[2] > 1:
            im = np.transpose(im, (2, 0, 1))

        header_dict = {}
        fk = meta[0].get('FITSKeywords', {})
        for kw_name, kw_values in fk.items():
            if kw_values:
                val = kw_values[0].get('value', '')
                val = self._parse_fits_value(val)
                header_dict[kw_name] = val

        return im, header_dict

    def _read_manual(self):
        """Manual XISF reader supporting all codecs."""
        with open(self.filepath, 'rb') as f:
            sig = f.read(8)
            if sig != b'XISF0100':
                raise ValueError("Not a valid XISF file")

            header_length = struct.unpack('<I', f.read(4))[0]
            f.read(4)  # reserved

            xml_bytes = f.read(header_length)
            xml_string = xml_bytes.rstrip(b'\x00').decode('utf-8')
            if xml_string.startswith('<?xml'):
                xml_string = xml_string[xml_string.index('?>') + 2:].strip()

            root = ET.fromstring(xml_string)
            ns = {'xisf': 'http://www.pixinsight.com/xisf'}
            image = root.find('xisf:Image', ns) or root.find('Image')
            if image is None:
                raise ValueError("No <Image> element in XISF")

            # Geometry
            geometry = image.get('geometry', '0:0:1')
            gparts = geometry.split(':')
            width, height = int(gparts[0]), int(gparts[1])
            channels = int(gparts[2]) if len(gparts) > 2 else 1

            # Sample format
            sample_format = image.get('sampleFormat', 'Float32')
            dtype_map = {
                'UInt8': np.uint8, 'UInt16': np.uint16, 'UInt32': np.uint32,
                'Int16': np.int16, 'Int32': np.int32,
                'Float32': np.float32, 'Float64': np.float64,
            }
            dtype = dtype_map.get(sample_format, np.float32)
            item_size = np.dtype(dtype).itemsize

            # Compression
            compression = image.get('compression', '')
            uses_shuffle = '+sh' in compression or 'byte-shuffling' in compression
            codec = 'none'
            if 'zlib' in compression:
                codec = 'zlib'
            elif 'zstd' in compression or 'zstandard' in compression:
                codec = 'zstd'
            elif 'lz4-hc' in compression:
                codec = 'lz4_hc'
            elif 'lz4' in compression:
                codec = 'lz4'

            # Parse uncompressed size from compression attribute
            comp_parts = compression.replace('+sh', '').replace('-hc', '_hc').split(':')
            uncompressed_size = width * height * channels * item_size
            if len(comp_parts) > 1:
                try:
                    uncompressed_size = int(comp_parts[1])
                except ValueError:
                    pass

            # Data location
            location = image.get('location', '')
            if not location.startswith('attachment:'):
                raise ValueError(f"Unsupported location: {location}")
            loc_parts = location[11:].split(':')
            data_offset = int(loc_parts[0])
            compressed_size = int(loc_parts[1]) if len(loc_parts) > 1 else 0

            # Read compressed data
            f.seek(data_offset)
            raw_read = f.read(compressed_size)

        # Decompress
        raw_data = decompress_data(raw_read, codec, uncompressed_size,
                                   uses_shuffle, item_size)

        # Convert to numpy array
        data = np.frombuffer(raw_data, dtype=dtype)
        if channels == 1:
            data = data.reshape(height, width)
        else:
            data = data.reshape(channels, height, width)

        # Extract FITSKeywords
        header_dict = {}
        for kw in (image.findall('xisf:FITSKeyword', ns) or
                   image.findall('FITSKeyword')):
            name = kw.get('name', '')
            val = kw.get('value', '')
            val = self._parse_fits_value(val)
            header_dict[name] = val

        return data, header_dict

    @staticmethod
    def _parse_fits_value(val):
        """Parse a FITS keyword value string."""
        if val.startswith("'") and val.endswith("'"):
            return val[1:-1].rstrip()
        elif val == 'T':
            return True
        elif val == 'F':
            return False
        else:
            try:
                if '.' in val or 'E' in val.upper():
                    return float(val)
                else:
                    return int(val)
            except (ValueError, TypeError):
                return val


# ============================================================================
# CONVERSION FUNCTIONS - All format combinations
# ============================================================================

def fits_to_xisf(fits_path, output_path=None, profile='zlib_6',
                 header_overrides=None):
    """Convert a FITS file to XISF with the specified compression profile.

    Args:
        fits_path: Path to input FITS/FIT file
        output_path: Path to output XISF (default: same name, .xisf extension)
        profile: Compression profile key from COMPRESSION_PROFILES
        header_overrides: dict of header keywords to add/override

    Returns:
        dict with status, sizes, ratio, etc.
    """
    if not ASTROPY_AVAILABLE:
        return {'status': 'failed', 'message': 'astropy not available'}

    try:
        prof = COMPRESSION_PROFILES.get(profile, COMPRESSION_PROFILES['zlib_6'])

        with astropy_fits.open(fits_path, memmap=False) as hdul:
            data = hdul[0].data
            header = hdul[0].header.copy()

        if data is None:
            return {'status': 'skipped', 'message': 'No image data',
                    'file': str(fits_path)}

        # Apply header overrides
        if header_overrides:
            for k, v in header_overrides.items():
                header[k] = v

        data = data.copy()
        if not data.flags['C_CONTIGUOUS']:
            data = np.ascontiguousarray(data)
        if data.dtype.byteorder == '>':
            data = data.byteswap().newbyteorder()

        if output_path is None:
            output_path = str(Path(fits_path).with_suffix('.xisf'))

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        original_size = os.path.getsize(fits_path)

        writer = XISFWriter(output_path, codec=prof['codec'],
                            level=prof['level'], shuffle=prof['shuffle'])
        info = writer.write_image(data, header)

        xisf_size = os.path.getsize(output_path)

        return {
            'status': 'success',
            'file': os.path.basename(fits_path),
            'output': output_path,
            'original_size': original_size,
            'compressed_size': xisf_size,
            'ratio': (1 - xisf_size / original_size) * 100 if original_size > 0 else 0,
            'codec': prof['codec'],
        }

    except Exception as e:
        return {'status': 'failed', 'message': str(e), 'file': str(fits_path)}


def xisf_to_fits(xisf_path, output_path=None, header_overrides=None):
    """Convert XISF to standard uncompressed FITS."""
    if not ASTROPY_AVAILABLE:
        return {'status': 'failed', 'message': 'astropy not available'}

    try:
        reader = XISFReader(xisf_path)
        data, metadata = reader.read_image()

        if output_path is None:
            output_path = str(Path(xisf_path).with_suffix('.fits'))

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        hdu = astropy_fits.PrimaryHDU(data)
        for key, value in metadata.items():
            if not key.endswith('_COMMENT'):
                try:
                    hdu.header[key] = value
                except Exception:
                    pass

        if header_overrides:
            for k, v in header_overrides.items():
                hdu.header[k] = v

        # Use silentfix: XISF metadata may contain Python booleans (True/False)
        # which are invalid in FITS headers (standard requires T/F strings).
        # silentfix lets astropy auto-correct these without raising errors.
        hdu.writeto(output_path, overwrite=True, output_verify='silentfix')

        return {
            'status': 'success',
            'file': os.path.basename(xisf_path),
            'output': output_path,
        }

    except Exception as e:
        return {'status': 'failed', 'message': str(e), 'file': str(xisf_path)}


def fits_to_fz(fits_path, output_path=None):
    """Compress FITS to FITS.FZ using fpack (tile compression via astropy)."""
    if not ASTROPY_AVAILABLE:
        return {'status': 'failed', 'message': 'astropy not available'}

    try:
        with astropy_fits.open(fits_path, memmap=False) as hdul:
            data = hdul[0].data
            header = hdul[0].header.copy()

        if data is None:
            return {'status': 'skipped', 'message': 'No image data'}

        if output_path is None:
            output_path = str(fits_path) + '.fz'

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        original_size = os.path.getsize(fits_path)

        # Create compressed HDU
        comp_hdu = astropy_fits.CompImageHDU(data=data, header=header,
                                             compression_type='RICE_1')
        hdul_out = astropy_fits.HDUList([astropy_fits.PrimaryHDU(), comp_hdu])
        hdul_out.writeto(output_path, overwrite=True)

        fz_size = os.path.getsize(output_path)

        return {
            'status': 'success',
            'file': os.path.basename(fits_path),
            'output': output_path,
            'original_size': original_size,
            'compressed_size': fz_size,
            'ratio': (1 - fz_size / original_size) * 100 if original_size > 0 else 0,
        }

    except Exception as e:
        return {'status': 'failed', 'message': str(e), 'file': str(fits_path)}


def fz_to_fits(fz_path, output_path=None):
    """Decompress FITS.FZ to standard FITS."""
    if not ASTROPY_AVAILABLE:
        return {'status': 'failed', 'message': 'astropy not available'}

    try:
        with astropy_fits.open(fz_path, memmap=False) as hdul:
            # Find the compressed image HDU
            data = None
            header = None
            for hdu in hdul:
                if isinstance(hdu, astropy_fits.CompImageHDU):
                    data = hdu.data.copy()
                    header = hdu.header.copy()
                    break

            if data is None:
                # Try primary HDU
                data = hdul[0].data
                header = hdul[0].header.copy() if data is not None else None

        if data is None:
            return {'status': 'skipped', 'message': 'No image data'}

        if output_path is None:
            output_path = str(fz_path).replace('.fits.fz', '.fits').replace('.fz', '.fits')

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        hdu = astropy_fits.PrimaryHDU(data=data, header=header)
        hdu.writeto(output_path, overwrite=True)

        return {
            'status': 'success',
            'file': os.path.basename(fz_path),
            'output': output_path,
        }

    except Exception as e:
        return {'status': 'failed', 'message': str(e), 'file': str(fz_path)}


def xisf_to_fz(xisf_path, output_path=None):
    """Convert XISF to FITS.FZ (decompress XISF then recompress as RICE)."""
    try:
        reader = XISFReader(xisf_path)
        data, metadata = reader.read_image()

        if output_path is None:
            output_path = str(Path(xisf_path).with_suffix('.fits.fz'))

        header = astropy_fits.Header()
        for k, v in metadata.items():
            if not k.endswith('_COMMENT'):
                try:
                    header[k] = v
                except Exception:
                    pass

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

        comp_hdu = astropy_fits.CompImageHDU(data=data, header=header,
                                             compression_type='RICE_1')
        hdul_out = astropy_fits.HDUList([astropy_fits.PrimaryHDU(), comp_hdu])
        hdul_out.writeto(output_path, overwrite=True)

        return {'status': 'success', 'file': os.path.basename(xisf_path),
                'output': output_path}

    except Exception as e:
        return {'status': 'failed', 'message': str(e), 'file': str(xisf_path)}


def fz_to_xisf(fz_path, output_path=None, profile='zlib_6'):
    """Convert FITS.FZ to XISF."""
    try:
        result = fz_to_fits(fz_path, output_path=None)  # temp FITS in memory
        if result['status'] != 'success':
            return result

        # Read the decompressed data directly
        with astropy_fits.open(fz_path, memmap=False) as hdul:
            data = None
            header = None
            for hdu in hdul:
                if isinstance(hdu, astropy_fits.CompImageHDU):
                    data = hdu.data.copy()
                    header = hdu.header.copy()
                    break
            if data is None:
                data = hdul[0].data
                header = hdul[0].header.copy() if data is not None else None

        if data is None:
            return {'status': 'skipped', 'message': 'No image data'}

        if output_path is None:
            base = str(fz_path).replace('.fits.fz', '').replace('.fz', '')
            output_path = base + '.xisf'

        prof = COMPRESSION_PROFILES.get(profile, COMPRESSION_PROFILES['zlib_6'])
        writer = XISFWriter(output_path, codec=prof['codec'],
                            level=prof['level'], shuffle=prof['shuffle'])
        writer.write_image(data, header)

        return {'status': 'success', 'file': os.path.basename(fz_path),
                'output': output_path}

    except Exception as e:
        return {'status': 'failed', 'message': str(e), 'file': str(fz_path)}


def recompress_xisf(xisf_path, output_path=None, profile='zlib_6'):
    """Re-compress an XISF file with a different codec/level."""
    try:
        reader = XISFReader(xisf_path)
        data, metadata = reader.read_image()

        if output_path is None:
            output_path = xisf_path  # in-place

        header = astropy_fits.Header() if ASTROPY_AVAILABLE else None
        if header is not None:
            for k, v in metadata.items():
                if not k.endswith('_COMMENT'):
                    try:
                        header[k] = v
                    except Exception:
                        pass

        prof = COMPRESSION_PROFILES.get(profile, COMPRESSION_PROFILES['zlib_6'])
        tmp_path = output_path + '.tmp_recomp'
        writer = XISFWriter(tmp_path, codec=prof['codec'],
                            level=prof['level'], shuffle=prof['shuffle'])
        writer.write_image(data, header)

        os.replace(tmp_path, output_path)

        return {'status': 'success', 'file': os.path.basename(xisf_path),
                'output': output_path, 'codec': prof['codec']}

    except Exception as e:
        if os.path.exists(str(xisf_path) + '.tmp_recomp'):
            try:
                os.remove(str(xisf_path) + '.tmp_recomp')
            except Exception:
                pass
        return {'status': 'failed', 'message': str(e), 'file': str(xisf_path)}


# ============================================================================
# BATCH CONVERSION
# ============================================================================

def convert_batch(source_dir, conversion_type, profile='zlib_6',
                  backup_dir=None, output_dir=None, workers=4,
                  progress_callback=None, stop_event=None):
    """Batch convert files in a directory.

    Args:
        source_dir: Source directory to scan recursively
        conversion_type: One of 'fits_to_xisf', 'xisf_to_fits', 'fits_to_fz',
                        'fz_to_fits', 'xisf_to_fz', 'fz_to_xisf', 'recompress_xisf'
        profile: Compression profile key
        backup_dir: Where to move originals after conversion (optional)
        output_dir: Where to write converted files (default: same location)
        workers: Number of parallel workers
        progress_callback: callable(current, total, message)
        stop_event: threading.Event to request stop

    Returns:
        dict with statistics
    """
    import shutil

    ext_map = {
        'fits_to_xisf': ('.fits', '.fit', '.fts'),
        'xisf_to_fits': ('.xisf', '.xifs', '.xif'),
        'fits_to_fz': ('.fits', '.fit', '.fts'),
        'fz_to_fits': ('.fits.fz', '.fz'),
        'xisf_to_fz': ('.xisf', '.xifs', '.xif'),
        'fz_to_xisf': ('.fits.fz', '.fz'),
        'recompress_xisf': ('.xisf', '.xifs', '.xif'),
    }

    extensions = ext_map.get(conversion_type, ())

    # Find files
    files = []
    skip_dirs = {'astronomical_analysis_', 'duplicates_', 'fits_originals_'}
    for root, dirs, filenames in os.walk(source_dir):
        dirs[:] = [d for d in dirs if not any(d.startswith(s) for s in skip_dirs)]
        for fname in filenames:
            fl = fname.lower()
            if any(fl.endswith(ext) for ext in extensions):
                files.append(os.path.join(root, fname))

    stats = {
        'total': len(files), 'converted': 0, 'failed': 0, 'skipped': 0,
        'total_original_size': 0, 'total_compressed_size': 0,
        'errors': [],
    }

    if not files:
        return stats

    func_map = {
        'fits_to_xisf': lambda fp: fits_to_xisf(fp, profile=profile),
        'xisf_to_fits': lambda fp: xisf_to_fits(fp),
        'fits_to_fz': lambda fp: fits_to_fz(fp),
        'fz_to_fits': lambda fp: fz_to_fits(fp),
        'xisf_to_fz': lambda fp: xisf_to_fz(fp),
        'fz_to_xisf': lambda fp: fz_to_xisf(fp, profile=profile),
        'recompress_xisf': lambda fp: recompress_xisf(fp, profile=profile),
    }

    convert_func = func_map.get(conversion_type)
    if not convert_func:
        return stats

    processed = 0
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(convert_func, fp): fp for fp in files}

        for future in as_completed(futures):
            if stop_event and stop_event.is_set():
                break

            result = future.result()
            processed += 1

            if result['status'] == 'success':
                stats['converted'] += 1
                if 'original_size' in result:
                    stats['total_original_size'] += result['original_size']
                if 'compressed_size' in result:
                    stats['total_compressed_size'] += result['compressed_size']

                # Move original to backup if requested
                if backup_dir:
                    src = futures[future]
                    rel = os.path.relpath(src, source_dir)
                    bkp = os.path.join(backup_dir, rel)
                    os.makedirs(os.path.dirname(bkp), exist_ok=True)
                    try:
                        shutil.move(src, bkp)
                    except Exception:
                        pass

            elif result['status'] == 'failed':
                stats['failed'] += 1
                stats['errors'].append({
                    'file': result.get('file', ''),
                    'error': result.get('message', 'Unknown error'),
                })
            else:
                stats['skipped'] += 1

            if progress_callback:
                progress_callback(processed, stats['total'],
                                  result.get('file', ''))

    return stats
