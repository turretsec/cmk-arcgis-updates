import json
import datetime
from typing import Optional

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Metric,
    Result,
    Service,
    State,
    StringTable,
)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

Section = Optional[dict]

# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

def parse_arcgis_updates(string_table: StringTable) -> Section:
    if not string_table:
        return None
    try:
        return json.loads(string_table[0][0])
    except (json.JSONDecodeError, IndexError):
        return None


agent_section_arcgis_updates = AgentSection(
    name          = 'arcgis_updates',
    parse_function = parse_arcgis_updates,
)

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_arcgis_updates(section: Section) -> DiscoveryResult:
    if section is None:
        return
    for comp in section.get('components', []):
        yield Service(item=f"{comp['display']} {comp['version']}")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _oldest_patch_age(patches: dict) -> Optional[int]:
    """Age in days of the oldest unapplied patch, or None if dates cannot be parsed."""
    today  = datetime.date.today()
    oldest = None
    for p in patches.values():
        try:
            released = datetime.datetime.strptime(p.get('ReleaseDate', ''), '%m/%d/%Y').date()
            age      = (today - released).days
            oldest   = age if oldest is None else max(oldest, age)
        except ValueError:
            pass
    return oldest


def _patch_word(n: int) -> str:
    return 'patch' if n == 1 else 'patches'


def _patch_details(patches: dict) -> str:
    """Build a multiline details string listing each missing patch."""
    today = datetime.date.today()
    lines = []
    for qid, p in sorted(patches.items()):
        name     = p.get('Name', qid)
        critical = ' [SECURITY]' if p.get('Critical', '').lower() == 'security' else ''
        age_str  = ''
        try:
            released = datetime.datetime.strptime(p.get('ReleaseDate', ''), '%m/%d/%Y').date()
            age_str  = f' ({(today - released).days}d old)'
        except ValueError:
            pass
        lines.append(f'{qid}{critical}{age_str}: {name}')
    return '\n'.join(lines)

# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------

def check_arcgis_updates(item: str, params: dict, section: Section) -> CheckResult:
    if section is None:
        yield Result(state=State.UNKNOWN, summary='No data from agent')
        return

    comp = None
    for c in section.get('components', []):
        if f"{c['display']} {c['version']}" == item:
            comp = c
            break

    if comp is None:
        yield Result(state=State.UNKNOWN, summary='Component not found in agent output')
        return

    feed_error = section.get('feed_error')
    feed_stale = section.get('feed_stale', False)
    available  = comp.get('available', {})
    applied    = set(comp.get('applied', []))

    # Feed stale - note it but continue evaluation with cached data
    if feed_stale and feed_error:
        yield Result(state=State.OK, summary=f'Patch feed: using stale cache ({feed_error})')

    # Feed completely unavailable - no data to evaluate
    if feed_error and not feed_stale and not available:
        yield Result(state=State.WARN, summary=f'Patch feed unavailable: {feed_error}')
        yield Metric('missing_patches', 0)
        return

    # Version not yet in the feed
    if not available:
        yield Result(state=State.OK, summary='No patches in feed for this version')
        yield Metric('missing_patches', 0)
        return

    missing = {qid: p for qid, p in available.items() if qid not in applied}

    if not missing:
        yield Result(
            state   = State.OK,
            summary = f'Up to date ({len(applied)}/{len(available)})',
        )
        yield Metric('missing_patches', 0)
        return

    security_missing = [
        qid for qid, p in missing.items()
        if p.get('Critical', '').lower() == 'security'
    ]
    oldest_age = _oldest_patch_age(missing)

    n_missing  = len(missing)
    n_sec      = len(security_missing)
    n_other    = n_missing - n_sec
    details    = _patch_details(missing)

    yield Metric('missing_patches', n_missing)

    if security_missing:
        if n_other > 0:
            summary = f'{n_sec} security + {n_other} other {_patch_word(n_other)} missing'
        else:
            summary = f'{n_sec} security {_patch_word(n_sec)} missing'
        yield Result(state=State.CRIT, summary=summary, details=details)
        return

    crit_age_days = params.get('crit_age_days', 90)
    if oldest_age is not None and oldest_age >= crit_age_days:
        yield Result(
            state   = State.CRIT,
            summary = f'{n_missing} {_patch_word(n_missing)} missing, oldest {oldest_age}d',
            details = details,
        )
        return

    summary = f'{n_missing} {_patch_word(n_missing)} available'

    if params.get('warn_on_available', True):
        yield Result(state=State.WARN, summary=summary, details=details)
        return

    yield Result(state=State.OK, summary=summary, details=details)


check_plugin_arcgis_updates = CheckPlugin(
    name                    = 'arcgis_updates',
    service_name            = '%s Patch Status',
    discovery_function      = discover_arcgis_updates,
    check_function          = check_arcgis_updates,
    check_default_parameters = {
        'warn_on_available': True,
        'crit_age_days':     90,
    },
    check_ruleset_name      = 'arcgis_updates',
)