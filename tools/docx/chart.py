"""Native Word chart XML. python-docx 1.2 has no chart API."""

from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape

_AXES = """
<c:catAx>
  <c:axId val="1"/>
  <c:scaling><c:orientation val="minMax"/></c:scaling>
  <c:delete val="0"/>
  <c:axPos val="b"/>
  <c:majorTickMark val="out"/>
  <c:minorTickMark val="none"/>
  <c:tickLblPos val="nextTo"/>
  <c:crossAx val="2"/>
  <c:crosses val="autoZero"/>
  <c:auto val="1"/>
  <c:lblAlgn val="ctr"/>
  <c:lblOffset val="100"/>
  <c:noMultiLvlLbl val="0"/>
</c:catAx>
<c:valAx>
  <c:axId val="2"/>
  <c:scaling><c:orientation val="minMax"/></c:scaling>
  <c:delete val="0"/>
  <c:axPos val="l"/>
  <c:majorGridlines/>
  <c:majorTickMark val="out"/>
  <c:minorTickMark val="none"/>
  <c:tickLblPos val="nextTo"/>
  <c:crossAx val="1"/>
  <c:crosses val="autoZero"/>
  <c:crossBetween val="between"/>
</c:valAx>
""".strip()


def chart_xml(block: dict[str, Any]) -> str:
    kind = str(block.get("chart") or "column")
    categories = [str(item) for item in block.get("categories") or []]
    series = list(block.get("series") or [])
    if kind == "pie":
        series = series[:1]
    plot = _plot(kind, categories, series)
    title = str(block.get("title") or "").strip()
    title_xml = f"<c:title>{_rich(title)}<c:overlay val=\"0\"/></c:title>" if title else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<c:chart>"
        f"{title_xml}"
        '<c:legend><c:legendPos val="b"/><c:overlay val="0"/></c:legend>'
        f"<c:plotArea><c:layout/>{plot}</c:plotArea>"
        '<c:plotVisOnly val="1"/>'
        "</c:chart></c:chartSpace>"
    )


def _plot(kind: str, categories: list[str], series: list[dict[str, Any]]) -> str:
    body = "".join(
        _series(index, item, categories, scatter=kind == "scatter")
        for index, item in enumerate(series)
    )
    if kind == "pie":
        return f'<c:pieChart><c:varyColors val="1"/>{body}</c:pieChart>'
    if kind == "line":
        return (
            '<c:lineChart><c:grouping val="standard"/><c:varyColors val="0"/>'
            f"{body}<c:marker val=\"1\"/><c:axId val=\"1\"/><c:axId val=\"2\"/></c:lineChart>{_AXES}"
        )
    if kind == "area":
        return (
            '<c:areaChart><c:grouping val="standard"/><c:varyColors val="0"/>'
            f'{body}<c:axId val="1"/><c:axId val="2"/></c:areaChart>{_AXES}'
        )
    if kind == "scatter":
        return (
            '<c:scatterChart><c:scatterStyle val="lineMarker"/><c:varyColors val="0"/>'
            f'{body}<c:axId val="1"/><c:axId val="2"/></c:scatterChart>{_AXES}'
        )
    direction = "bar" if kind == "bar" else "col"
    return (
        f'<c:barChart><c:barDir val="{direction}"/><c:grouping val="clustered"/>'
        f'<c:varyColors val="0"/>{body}<c:axId val="1"/><c:axId val="2"/></c:barChart>{_AXES}'
    )


def _series(index: int, item: dict[str, Any], categories: list[str], *, scatter: bool) -> str:
    name = escape(str(item.get("name") or "Series"))
    values = list(item.get("values") or [])
    if scatter:
        xs = [_x_value(category, position) for position, category in enumerate(categories, 1)]
        x_pts = _num_pts(xs)
        y_pts = _num_pts(values)
        return (
            f'<c:ser><c:idx val="{index}"/><c:order val="{index}"/>'
            f"<c:tx><c:v>{name}</c:v></c:tx>"
            f'<c:xVal><c:numLit><c:ptCount val="{len(xs)}"/>{x_pts}</c:numLit></c:xVal>'
            f'<c:yVal><c:numLit><c:ptCount val="{len(values)}"/>{y_pts}</c:numLit></c:yVal>'
            "</c:ser>"
        )
    cats = "".join(
        f'<c:pt idx="{position}"><c:v>{escape(category)}</c:v></c:pt>'
        for position, category in enumerate(categories)
    )
    vals = _num_pts(values)
    return (
        f'<c:ser><c:idx val="{index}"/><c:order val="{index}"/>'
        f"<c:tx><c:v>{name}</c:v></c:tx>"
        f'<c:cat><c:strLit><c:ptCount val="{len(categories)}"/>{cats}</c:strLit></c:cat>'
        f'<c:val><c:numLit><c:ptCount val="{len(values)}"/>{vals}</c:numLit></c:val>'
        "</c:ser>"
    )


def _num_pts(values: list[Any]) -> str:
    return "".join(
        f'<c:pt idx="{position}"><c:v>{value}</c:v></c:pt>' for position, value in enumerate(values)
    )


def _x_value(category: str, position: int) -> float:
    try:
        return float(category)
    except (TypeError, ValueError):
        return float(position)


def _rich(text: str) -> str:
    safe = escape(text)
    return (
        "<c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p>"
        '<a:pPr><a:defRPr/></a:pPr>'
        f'<a:r><a:rPr lang="en-US"/><a:t>{safe}</a:t></a:r>'
        "</a:p></c:rich></c:tx>"
    )
