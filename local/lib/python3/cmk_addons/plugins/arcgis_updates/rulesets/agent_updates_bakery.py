from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import (
    DefaultValue,
    DictElement,
    Dictionary,
    InputHint,
    Integer,
    String,
)
from cmk.rulesets.v1.rule_specs import AgentConfig, Topic


def _form_arcgis_updates_bakery() -> Dictionary:
    return Dictionary(
        title     = Title('ArcGIS Enterprise: Patch Update Check'),
        help_text = Help(
            'Deploys the arcgis_updates agent plugin to Windows hosts. '
            'The plugin discovers ArcGIS Enterprise components from the Windows '
            'registry and compares installed patch QFE_IDs against the Esri patch '
            'notification feed. One service is created per installed component. '
            'Patch status thresholds are configured under '
            'Setup -> Service monitoring rules -> Applications -> '
            'ArcGIS Enterprise: Patch Status. '
            'All settings here are optional.'
        ),
        elements  = {
            'patches_url': DictElement(
                required       = False,
                parameter_form = String(
                    title     = Title('Patch feed URL'),
                    help_text = Help(
                        'URL for the Esri patch notification JSON feed. '
                        'Override with an internal mirror URL if your ArcGIS '
                        'hosts cannot reach the internet directly.'
                    ),
                    prefill = InputHint(
                        'https://content.esri.com/patch_notification/patches.json'
                    ),
                ),
            ),
            'cache_ttl': DictElement(
                required       = False,
                parameter_form = Integer(
                    title     = Title('Patch feed cache TTL (seconds)'),
                    help_text = Help(
                        'How long to cache the patch feed locally before re-fetching. '
                        'The cached copy is also used as a fallback if the feed is '
                        'unreachable. Default: 3600.'
                    ),
                    prefill = DefaultValue(3600),
                ),
            ),
            'request_timeout': DictElement(
                required       = False,
                parameter_form = Integer(
                    title     = Title('Feed request timeout (seconds)'),
                    help_text = Help('HTTP timeout when fetching the patch feed. Default: 15.'),
                    prefill   = DefaultValue(15),
                ),
            ),
        },
    )


rule_spec_arcgis_updates_bakery = AgentConfig(
    name           = 'arcgis_updates',
    title          = Title('ArcGIS Enterprise: Patch Update Check'),
    topic          = Topic.APPLICATIONS,
    parameter_form = _form_arcgis_updates_bakery,
)