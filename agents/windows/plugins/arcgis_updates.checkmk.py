import sys
import re
import json
import time
import configparser
import urllib.request
from typing import Optional
from pathlib import Path

# ---------------------------------------------------------------------------
# Platform Guard
# ---------------------------------------------------------------------------

try:
    import winreg
    WINDOWS = True
except ImportError:
    WINDOWS = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR  = Path(__file__).parent
CACHE_FILE  = SCRIPT_DIR / ".arcgis_patch_cache.json"
CONFIG_FILE = SCRIPT_DIR / "arcgis_updates.cfg"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_PATCHES_URL = "https://content.esri.com/patch_notification/patches.json"
DEFAULT_CACHE_TTL   = 3600   # seconds
DEFAULT_TIMEOUT     = 15     # seconds

# ---------------------------------------------------------------------------
# Component Mapping
# ---------------------------------------------------------------------------
# Used ONLY when a component has the QFEPatchFinder / QFEARP marker but zero
# patches applied (can't auto-detect the QFE prefix from existing IDs).
#
# Entries confirmed from real registry exports are marked [VERIFIED].
# Others are educated guesses on key name pattern and/or QFE prefix.
# I do not have access to all ArcGIS components,
# so outside contributions are very welcome!
#
# Format: (key_name_regex, display_name, qfe_prefix, version_source)
#   version_source: 'keyname' = captured from regex group 1
#                   'RealVersion' = read from the registry value
#---------------------------------------------------------------------------

KNOWN_COMPONENTS = [
    # [VERIFIED] ArcGIS Server - key name encodes version e.g. "Server11.5"
    (re.compile(r'^Server(\d+\.\d+(?:\.\d+)?)$', re.I),
     'ArcGIS Server', 'S', 'keyname'),

    # [VERIFIED] Portal for ArcGIS
    (re.compile(r'^Portal for ArcGIS$', re.I),
     'Portal for ArcGIS', 'PFA', 'RealVersion'),

    # [VERIFIED] ArcGIS Data Store
    (re.compile(r'^ArcGIS Data Store$', re.I),
     'ArcGIS Data Store', 'DS', 'RealVersion'),

    # [UNVERIFIED]
    (re.compile(r'^GeoEvent', re.I),
     'ArcGIS GeoEvent Server', 'GES', 'RealVersion'),

    # [UNVERIFIED]
    (re.compile(r'^Web Adaptor', re.I),
     'ArcGIS Web Adaptor', 'WA', 'RealVersion'),

    # [UNVERIFIED]
    (re.compile(r'^Notebook Server', re.I),
     'ArcGIS Notebook Server', 'NBS', 'RealVersion'),

    # [UNVERIFIED]
    (re.compile(r'^Mission Server', re.I),
     'ArcGIS Mission Server', 'MS', 'RealVersion'),

    # [UNVERIFIED]
    (re.compile(r'^Video Server', re.I),
     'ArcGIS Video Server', 'VS', 'RealVersion'),

    # [UNVERIFIED]
    (re.compile(r'^Knowledge Server', re.I),
     'ArcGIS Knowledge Server', 'KS', 'RealVersion'),
]

# Lookup from auto-detected QFE prefix to human-readable display name.
QFE_PREFIX_DISPLAY = {
    'S':   'ArcGIS Server',
    'PFA': 'Portal for ArcGIS',
    'DS':  'ArcGIS Data Store',
    'GES': 'ArcGIS GeoEvent Server',
    'WA':  'ArcGIS Web Adaptor',
    'NBS': 'ArcGIS Notebook Server',
    'MS':  'ArcGIS Mission Server',
    'VS':  'ArcGIS Video Server',
    'KS':  'ArcGIS Knowledge Server',
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_config() -> dict:
    cfg = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        cfg.read(CONFIG_FILE, encoding='utf-8')
    s = cfg['arcgis_updates'] if 'arcgis_updates' in cfg else {}
    return {
        'patches_url': s.get('patches_url', DEFAULT_PATCHES_URL),
        'cache_ttl':   int(s.get('cache_ttl', DEFAULT_CACHE_TTL)),
        'timeout':     int(s.get('request_timeout', DEFAULT_TIMEOUT)),
    }

# ---------------------------------------------------------------------------
# Patch Feed
# ---------------------------------------------------------------------------

def load_feed(url: str, ttl: int, timeout: int) -> tuple:
    """
    Returns (feed_data, stale: bool, error: str|None).
    stale=True means we are using an expired cache because the live fetch failed.
    """
    now = time.time()

    def _read_cache():
        if CACHE_FILE.exists():
            try:
                payload = json.loads(CACHE_FILE.read_bytes())
                return payload.get('data'), payload.get('fetched_at', 0)
            except Exception:
                pass
        return None, 0

    cached_data, fetched_at = _read_cache()
    if cached_data and (now - fetched_at) < ttl:
        return cached_data, False, None

    # Cache stale or missing - try live fetch
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.load(resp)
        CACHE_FILE.write_bytes(json.dumps({'fetched_at': now, 'data': data}).encode())
        return data, False, None
    except Exception as exc:
        if cached_data:
            return cached_data, True, str(exc)
        return None, False, str(exc)


def build_feed_index(feed_data: dict) -> dict:
    """
    Returns {version_str: {qfe_id: patch_dict}}.
    Example: {'11.5': {'S-115-P-1306': {...}, 'PFA-115-P-1287': {...}}}
    """
    index = {}
    for block in feed_data.get('Product', []):
        ver = block.get('version', '').strip()
        if ver:
            index[ver] = {
                p['QFE_ID']: p
                for p in block.get('patches', [])
                if 'QFE_ID' in p
            }
    return index


def version_to_code(version: str) -> str:
    """'11.5' -> '115', '10.9.1' -> '1091'"""
    return version.replace('.', '')


def get_available_patches(feed_index: dict, version: str, qfe_prefix: str) -> dict:
    """
    All feed patches for this version whose QFE_ID starts with
    '{prefix}-{ver_code}-', e.g. prefix='S', version='11.5' -> 'S-115-'
    """
    ver_code  = version_to_code(version)
    match_str = f"{qfe_prefix}-{ver_code}-"
    return {
        qid: p
        for qid, p in feed_index.get(version, {}).items()
        if qid.startswith(match_str)
    }

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REG_FLAGS  = winreg.KEY_READ | winreg.KEY_WOW64_64KEY if WINDOWS else 0
ESRI_SUBKEY = r"SOFTWARE\ESRI"


def _reg_value(key_handle, name: str):
    try:
        val, _ = winreg.QueryValueEx(key_handle, name)
        return val
    except OSError:
        return None


def _open_key(parent, subkey: str):
    try:
        return winreg.OpenKey(parent, subkey, access=_REG_FLAGS)
    except OSError:
        return None


def _enum_subkeys(key_handle) -> list:
    names = []
    idx   = 0
    while True:
        try:
            names.append(winreg.EnumKey(key_handle, idx))
            idx += 1
        except OSError:
            break
    return names


def _is_patchable(key_handle) -> bool:
    """
    Esri places QFEPatchFinder or QFEARP on every product key they intend
    to be patch-tracked. Either marker is sufficient.
    """
    return (
        _reg_value(key_handle, 'QFEPatchFinder') is not None or
        _reg_value(key_handle, 'QFEARP') is not None
    )


def _get_applied_patches(key_handle) -> set:
    """
    Enumerate Updates\\* subkeys and collect all QFE_ID values.
    Returns empty set if Updates doesn't exist or has no entries.
    """
    applied    = set()
    updates_key = _open_key(key_handle, 'Updates')
    if updates_key is None:
        return applied
    try:
        for patch_subkey_name in _enum_subkeys(updates_key):
            patch_key = _open_key(updates_key, patch_subkey_name)
            if patch_key:
                qfe_id = _reg_value(patch_key, 'QFE_ID')
                if qfe_id:
                    applied.add(qfe_id.strip())
                winreg.CloseKey(patch_key)
    finally:
        winreg.CloseKey(updates_key)
    return applied


def _prefix_from_qfe_ids(qfe_ids: set) -> Optional[str]:
    """
    Extract the product prefix from any applied QFE_ID.
    New format: PREFIX-VERCODE-P-NUM  e.g. S-115-P-1306 -> 'S'
                                           PFA-115-P-1287 -> 'PFA'
    """
    for qfe_id in sorted(qfe_ids):
        parts = qfe_id.split('-')
        # Expect at least 4 parts, third must be 'P'
        if len(parts) >= 4 and parts[2].upper() == 'P':
            return parts[0].upper()
    return None


def _normalize_version(version: str) -> str:
    """
    Strip trailing .0 so '11.5.0' -> '11.5' to match feed keys.
    Leaves '10.9.1' untouched.
    """
    parts = version.split('.')
    while len(parts) > 2 and parts[-1] == '0':
        parts.pop()
    return '.'.join(parts)


def _match_known(key_name: str, key_handle) -> tuple:
    """
    Try to match key_name against KNOWN_COMPONENTS.
    Returns (display, version, qfe_prefix) or (None, None, None).
    """
    for pattern, display, prefix, ver_source in KNOWN_COMPONENTS:
        m = pattern.match(key_name)
        if m:
            if ver_source == 'keyname':
                version = m.group(1)
            else:
                raw     = _reg_value(key_handle, 'RealVersion')
                version = _normalize_version(raw) if raw else None
            if version:
                return display, version, prefix
    return None, None, None


def discover_components() -> list:
    """
    Enumerate HKLM\\SOFTWARE\\ESRI and return a list of component dicts:
      {display, version, qfe_prefix, applied: set[str], key_name: str}
    """
    components = []

    esri_key = _open_key(winreg.HKEY_LOCAL_MACHINE, ESRI_SUBKEY)
    if esri_key is None:
        return components

    try:
        for key_name in _enum_subkeys(esri_key):
            comp_key = _open_key(esri_key, key_name)
            if comp_key is None:
                continue

            try:
                if not _is_patchable(comp_key):
                    continue

                applied              = _get_applied_patches(comp_key)
                display, version, qfe_prefix = None, None, None

                # Stage 1: auto-detect from applied QFE_IDs
                if applied:
                    qfe_prefix = _prefix_from_qfe_ids(applied)
                    if qfe_prefix:
                        raw = _reg_value(comp_key, 'RealVersion')
                        if raw:
                            version = _normalize_version(raw)
                        else:
                            # Server-style: version may be in the key name
                            m = re.match(r'^Server(\d+\.\d+(?:\.\d+)?)$', key_name, re.I)
                            version = m.group(1) if m else None
                        display = QFE_PREFIX_DISPLAY.get(qfe_prefix, f'ArcGIS ({key_name})')

                # Stage 2: zero-patch fallback
                if not all((display, version, qfe_prefix)):
                    display, version, qfe_prefix = _match_known(key_name, comp_key)

                if display and version and qfe_prefix:
                    components.append({
                        'key_name':   key_name,
                        'display':    display,
                        'version':    version,
                        'qfe_prefix': qfe_prefix,
                        'applied':    applied,
                    })

            finally:
                winreg.CloseKey(comp_key)

    finally:
        winreg.CloseKey(esri_key)

    return components

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not WINDOWS:
        sys.exit(0)

    cfg            = load_config()
    components_raw = discover_components()

    feed_data, stale, feed_error = load_feed(
        cfg['patches_url'], cfg['cache_ttl'], cfg['timeout']
    )

    feed_index = build_feed_index(feed_data) if feed_data is not None else {}

    components_out = []
    for comp in components_raw:
        available = get_available_patches(feed_index, comp['version'], comp['qfe_prefix'])
        components_out.append({
            'display':    comp['display'],
            'version':    comp['version'],
            'qfe_prefix': comp['qfe_prefix'],
            'applied':    sorted(comp['applied']),
            'available':  {
                qid: {k: p[k] for k in ('Name', 'Critical', 'ReleaseDate') if k in p}
                for qid, p in available.items()
            },
        })

    print('<<<arcgis_updates:sep(0)>>>')
    print(json.dumps({
        'feed_stale': stale,
        'feed_error': feed_error,
        'components': components_out,
    }))


if __name__ == '__main__':
    main()