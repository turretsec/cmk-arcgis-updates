from pathlib import Path
from typing import Generator

from cmk.base.plugins.bakery.bakery_api.v1 import (
    OS,
    Plugin,
    PluginConfig,
    register,
)


def _get_arcgis_updates_files(conf: dict) -> Generator:
    yield Plugin(
        base_os = OS.WINDOWS,
        source  = Path('arcgis_updates.checkmk.py'),
        target  = Path('arcgis_updates.checkmk.py'),
    )

    if conf:
        yield PluginConfig(
            base_os = OS.WINDOWS,
            lines   = _build_cfg_lines(conf),
            target  = Path('arcgis_updates.cfg'),
        )


def _build_cfg_lines(conf: dict) -> list:
    lines = ['[arcgis_updates]']

    if url := conf.get('patches_url'):
        lines.append(f'patches_url = {url}')

    if ttl := conf.get('cache_ttl'):
        lines.append(f'cache_ttl = {ttl}')

    if timeout := conf.get('request_timeout'):
        lines.append(f'request_timeout = {timeout}')

    return lines


register.bakery_plugin(
    name           = 'arcgis_updates',
    files_function = _get_arcgis_updates_files,
)