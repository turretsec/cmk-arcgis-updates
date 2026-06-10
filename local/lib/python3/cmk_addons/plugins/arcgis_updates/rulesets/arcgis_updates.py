from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import (
    BooleanChoice,
    DefaultValue,
    DictElement,
    Dictionary,
    Integer,
)
from cmk.rulesets.v1.rule_specs import CheckParameters, HostAndItemCondition, Topic


def _form_arcgis_updates() -> Dictionary:
    return Dictionary(
        title    = Title('ArcGIS Enterprise: Patch Status'),
        elements = {
            'warn_on_available': DictElement(
                required       = False,
                parameter_form = BooleanChoice(
                    title     = Title('Warn when non-critical patches are available'),
                    help_text = Help(
                        'Emit WARN when patches are available but not flagged as '
                        'security-critical. Disable to alert only on security patches '
                        'and overdue patches.'
                    ),
                    prefill = DefaultValue(True),
                ),
            ),
            'crit_age_days': DictElement(
                required       = False,
                parameter_form = Integer(
                    title       = Title('Days before CRIT for overdue patches'),
                    help_text   = Help(
                        'Emit CRIT when the oldest unapplied patch has been available '
                        'for more than this many days.'
                    ),
                    prefill     = DefaultValue(90),
                    unit_symbol = 'days',
                ),
            ),
        },
    )


rule_spec_arcgis_updates = CheckParameters(
    name           = 'arcgis_updates',
    title          = Title('ArcGIS Enterprise: Patch Status'),
    topic          = Topic.APPLICATIONS,
    parameter_form = _form_arcgis_updates,
    condition      = HostAndItemCondition(item_title=Title('ArcGIS component')),
)