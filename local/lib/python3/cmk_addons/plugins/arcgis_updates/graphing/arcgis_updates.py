from cmk.graphing.v1 import Title
from cmk.graphing.v1.graphs import Graph
from cmk.graphing.v1.metrics import Color, DecimalNotation, Metric, StrictPrecision, Unit
from cmk.graphing.v1.perfometers import Closed, FocusRange, Open, Perfometer

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

metric_arcgis_missing_patches = Metric(
    name  = 'missing_patches',
    title = Title('Missing patches'),
    unit  = Unit(DecimalNotation(''), StrictPrecision(0)),
    color = Color.ORANGE,
)

# ---------------------------------------------------------------------------
# Graphs
# ---------------------------------------------------------------------------

graph_arcgis_missing_patches = Graph(
    name         = 'arcgis_missing_patches',
    title        = Title('ArcGIS missing patches'),
    simple_lines = ['missing_patches'],
)

# ---------------------------------------------------------------------------
# Perfometers
# ---------------------------------------------------------------------------

perfometer_arcgis_missing_patches = Perfometer(
    name        = 'arcgis_missing_patches',
    focus_range = FocusRange(Closed(0), Open(10)),
    segments    = ['missing_patches'],
)