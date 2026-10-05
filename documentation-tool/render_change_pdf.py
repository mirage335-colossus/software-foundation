"""Render the prospective edit paths as a small, linked graphical handbook.

The input is a previously captured source model. This module performs no
collection, source modification, application build, or application execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote
from xml.sax.saxutils import escape
import re
import unicodedata


def _plain(value: Any) -> str:
    value = str(value if value is not None else "")
    value = value.replace("\u2013", "-").replace("\u2014", "-")
    value = value.replace("\u2018", "'").replace("\u2019", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    value = value.replace("\u2192", " -> ").replace("\u21d2", " -> ")
    value = value.replace("\u2190", " <- ").replace("\u2194", " <-> ")
    value = value.replace("\u00b7", " | ")
    return unicodedata.normalize("NFKD", value).encode("ascii", "backslashreplace").decode("ascii")


def _esc(value: Any) -> str:
    return escape(_plain(value), {'"': "&quot;"})


def _dest(kind: str, map_id: str, node_id: str = "") -> str:
    return kind + "-" + re.sub(r"[^A-Za-z0-9_-]", "_", map_id + "-" + node_id)


def _source_url(node: dict[str, Any]) -> str:
    return "../index.html#source/" + quote(str(node.get("file_id") or node.get("path", "")), safe="") + "/" + str(node.get("line") or 1)


def _symbol_url(node: dict[str, Any]) -> str:
    return "../index.html#symbol/" + quote(str(node.get("symbol_id", "")), safe="")


def render_change_pdfs(model: dict[str, Any], output: Path) -> list[str]:
    """Write the edit-path PDF beneath the caller's isolated output directory."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import (
            BaseDocTemplate, Flowable, Frame, KeepTogether, NextPageTemplate,
            PageBreak, PageTemplate, Paragraph, Spacer,
        )
    except ImportError as exc:
        raise ImportError("Edit-path PDF output needs ReportLab. Install the documentation "
                          "tool's requirements or run with --no-pdf.") from exc

    maps = model.get("change_maps", [])
    if not maps:
        raise ValueError("No change_maps are available for the edit-path PDF.")
    output = Path(output)
    pdf_dir = output / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    filename = pdf_dir / "00-edit-paths.pdf"
    page_w, page_h = landscape(letter)
    margin = 26
    body_w = page_w - margin * 2
    body_h = page_h - 91
    ink = colors.HexColor("#173849")
    muted = colors.HexColor("#4d616d")
    rule = colors.HexColor("#cad8df")
    role_colors = {
        "EDIT": (colors.HexColor("#fff0d5"), colors.HexColor("#ae741b")),
        "REUSE": (colors.HexColor("#eef3f5"), colors.HexColor("#77909b")),
        "DECISION": (colors.HexColor("#f0eafa"), colors.HexColor("#8063a5")),
        "NEW": (colors.HexColor("#e6f4ec"), colors.HexColor("#29805a")),
        "JUMP": (colors.HexColor("#e6effa"), colors.HexColor("#356caa")),
    }
    styles = {
        "body": ParagraphStyle("edit-body", fontName="Helvetica", fontSize=10,
                               leading=13.1, textColor=ink, spaceAfter=5),
        "small": ParagraphStyle("edit-small", fontName="Helvetica", fontSize=9.2,
                                leading=11.8, textColor=muted, spaceAfter=4),
        "heading": ParagraphStyle("edit-heading", fontName="Helvetica-Bold", fontSize=11,
                                  leading=14, textColor=ink, spaceBefore=8,
                                  spaceAfter=5, keepWithNext=True),
        "chapter": ParagraphStyle("edit-chapter", fontName="Helvetica-Bold", fontSize=15,
                                  leading=18, textColor=ink, spaceAfter=8,
                                  keepWithNext=True),
        "node-title": ParagraphStyle("edit-node-title", fontName="Helvetica-Bold",
                                     fontSize=9.4, leading=11.1, textColor=ink),
        "node-body": ParagraphStyle("edit-node-body", fontName="Helvetica", fontSize=9,
                                    leading=10.7, textColor=ink),
        "node-source": ParagraphStyle("edit-node-source", fontName="Helvetica", fontSize=9,
                                      leading=10.7, textColor=muted),
        "edge-key": ParagraphStyle("edit-edge-key", fontName="Helvetica", fontSize=9,
                                   leading=11.2, textColor=ink, spaceAfter=4),
        "question": ParagraphStyle("edit-question", fontName="Helvetica", fontSize=10,
                                   leading=12, textColor=muted),
    }
    for style in styles.values():
        style.splitLongWords = True

    def link(label: Any, target: str) -> str:
        return f'<link href="{_esc(target)}" color="#256b91">{_esc(label)}</link>'

    def paragraph(value: Any, style: str = "body", raw: bool = False) -> Any:
        return Paragraph(str(value) if raw else _esc(value), styles[style])

    def ref_text(reference: dict[str, Any]) -> str:
        path, line = reference.get("path", ""), reference.get("line")
        status = reference.get("status", "verified" if path and line else "missing")
        label = f"{path}:{line}" if line else str(path)
        if status == "missing":
            return "<b>Review required:</b> " + _esc(label or "source location was not captured")
        if status == "proposed":
            if path and line and reference.get("file_id"):
                return "<b>Existing source/example:</b> " + link(label, _source_url(reference))
            return "<b>Planned addition:</b> " + _esc(label or "new application code to add")
        rendered = link(label, _source_url(reference)) if path else "Source location not supplied"
        if reference.get("symbol_id"):
            rendered += " | " + link("function", _symbol_url(reference))
        prefix = "Read-only supplier evidence" if str(path).startswith("@") else "Source"
        return "<b>" + prefix + ":</b> " + rendered

    def primary_reference(node: dict[str, Any]) -> dict[str, Any]:
        """A missing related anchor does not erase a verified primary anchor."""
        if node.get("status") == "missing":
            for reference in node.get("references", []):
                if (reference.get("path"), reference.get("line")) == (node.get("path"), node.get("line")):
                    return reference
        return node

    class Heading(Paragraph):
        def __init__(self, text: str, destination: str, level: int, chapter: bool = False) -> None:
            super().__init__(_esc(text), styles["chapter" if chapter else "heading"])
            self.destination, self.level, self.label = destination, level, _plain(text)

    class EditDoc(BaseDocTemplate):
        def __init__(self) -> None:
            super().__init__(str(filename), pagesize=(page_w, page_h), leftMargin=margin,
                             rightMargin=margin, topMargin=54, bottomMargin=37,
                             title=f"{model.get('title', 'Software foundation')}: edit paths",
                             author="Local source-map generator",
                             subject="Prospective edits and verified source navigation")
            self.current_map = maps[0]
            full = Frame(margin, 37, body_w, body_h, leftPadding=0,
                         rightPadding=0, topPadding=0, bottomPadding=0)
            gap = 24
            col_w = (body_w - gap) / 2
            left = Frame(margin, 37, col_w, body_h, leftPadding=0,
                         rightPadding=0, topPadding=0, bottomPadding=0)
            right = Frame(margin + col_w + gap, 37, col_w, body_h,
                          leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
            self.addPageTemplates([
                PageTemplate(id="chart", frames=[full], onPage=self.decorate),
                PageTemplate(id="details", frames=[left, right], onPage=self.decorate),
            ])

        def decorate(self, c: Any, doc: Any) -> None:
            c.saveState()
            c.setFont("Helvetica-Bold", 16)
            c.setFillColor(ink)
            c.drawString(margin, page_h - 27, _plain(self.current_map.get("title", "Edit path")))
            c.setFont("Helvetica", 8)
            c.setFillColor(muted)
            c.drawRightString(page_w - margin, page_h - 27, f"Edit paths | {doc.page}")
            c.setStrokeColor(rule)
            c.line(margin, page_h - 38, page_w - margin, page_h - 38)
            c.line(margin, 28, page_w - margin, 28)
            c.setFont("Helvetica", 8)
            c.setFillColor(colors.HexColor("#256b91"))
            c.drawString(margin, 16, "Up to chart")
            c.linkRect("", _dest("chart", self.current_map["id"]),
                       (margin, 13, margin + 48, 24), relative=1)
            c.drawString(margin + 65, 16, "Offline explorer")
            c.linkURL("../index.html#change/" + quote(self.current_map["id"], safe=""),
                      (margin + 65, 13, margin + 127, 24), relative=1)
            generated = _plain(model.get("generated_at", "unknown date"))
            c.setFillColor(muted)
            c.drawRightString(page_w - margin, 16,
                              f"Snapshot {generated} | Generated on request; may be stale")
            c.restoreState()

        def afterFlowable(self, item: Any) -> None:
            if isinstance(item, Heading):
                self.canv.bookmarkPage(item.destination)
                self.canv.addOutlineEntry(item.label, item.destination, level=item.level,
                                          closed=item.level > 0)
            elif isinstance(item, Chart):
                self.canv.bookmarkPage(_dest("chart", item.map["id"]))
                self.canv.addOutlineEntry(_plain(item.map.get("title", "Edit path")),
                                          _dest("chart", item.map["id"]), level=0)

    class SetMap(Flowable):
        def __init__(self, map_value: dict[str, Any]) -> None:
            super().__init__()
            self.map = map_value
            self.width = 0
            self.height = 0

        def draw(self) -> None:
            self._doctemplate.current_map = self.map

    class Chart(Flowable):
        def __init__(self, map_value: dict[str, Any]) -> None:
            super().__init__()
            self.map = map_value
            self.width, self.height = body_w, body_h

        def wrap(self, aw: float, ah: float) -> tuple[float, float]:
            return self.width, self.height

        def text(self, text: str, x: float, top: float, width: float,
                 style: str, raw: bool = False) -> float:
            para = paragraph(text, style, raw)
            _, h = para.wrap(width, self.height)
            para.drawOn(self.canv, x, top - h)
            return h

        def arrow(self, points: list[tuple[float, float]], edge: dict[str, Any], number: int,
                  badge: tuple[float, float]) -> None:
            c = self.canv
            color = colors.HexColor("#2f6e9a") if edge.get("kind") == "runtime" else (
                colors.HexColor("#a37123") if edge.get("kind") == "conditional" else colors.HexColor("#576f7c"))
            c.setStrokeColor(color)
            c.setFillColor(color)
            c.setLineWidth(1.15)
            c.setDash(3, 2) if edge.get("kind") == "conditional" else c.setDash()
            path = c.beginPath()
            path.moveTo(*points[0])
            for point in points[1:]:
                path.lineTo(*point)
            c.drawPath(path)
            c.setDash()
            end, previous = points[-1], points[-2]
            dx, dy = end[0] - previous[0], end[1] - previous[1]
            if abs(dx) > abs(dy):
                sign = 1 if dx > 0 else -1
                arms = [(end[0] - sign * 5, end[1] + 3), (end[0] - sign * 5, end[1] - 3)]
            else:
                sign = 1 if dy > 0 else -1
                arms = [(end[0] + 3, end[1] - sign * 5), (end[0] - 3, end[1] - sign * 5)]
            for arm in arms:
                c.line(*end, *arm)
            bx, by = badge
            c.setFillColor(colors.white)
            c.setStrokeColor(color)
            c.roundRect(bx - 8, by - 6, 16, 12, 3, fill=1, stroke=1)
            c.setFillColor(color)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(bx, by - 3, str(number))

        def route(self, source: dict[str, Any], target: dict[str, Any], lane: int,
                  cell_w: float, cell_h: float, grid_top: float) -> tuple[list[tuple[float, float]], tuple[float, float]]:
            sx, sy, sw, sh = source["box"]
            tx, ty, tw, th = target["box"]
            sc, sr, tc, tr = source["column"], source["row"], target["column"], target["row"]
            smx, smy, tmx, tmy = sx + sw / 2, sy + sh / 2, tx + tw / 2, ty + th / 2
            if sr == tr and abs(sc - tc) == 1:
                start, end = ((sx + sw, smy), (tx, tmy)) if tc > sc else ((sx, smy), (tx + tw, tmy))
                return [start, end], ((start[0] + end[0]) / 2, smy)
            if sc == tc and abs(sr - tr) == 1:
                start, end = ((smx, sy), (tmx, ty + th)) if tr > sr else ((smx, sy + sh), (tmx, ty))
                return [start, end], (smx - 14, (start[1] + end[1]) / 2 + 1)
            # Column gutters and row gutters form a clear routing grid. For
            # longer edges, enter the target from the nearer vertical side.
            going_right = tc >= sc
            gutter_x = (sc + 1) * cell_w - 5 if going_right else sc * cell_w + 5
            start = (sx + sw, smy) if going_right else (sx, smy)
            corridor_y = grid_top - tr * cell_h + 5
            if corridor_y > grid_top + 3:
                corridor_y = grid_top + 3
            end = (tmx, ty + th)
            points = [start, (gutter_x, smy), (gutter_x, corridor_y),
                      (tmx, corridor_y), end]
            # Put edge-number badges into the row corridor, not onto text.
            badge = (gutter_x * 0.68 + tmx * 0.32, corridor_y)
            return points, badge

        def draw(self) -> None:
            c = self.canv
            question = self.map.get("question", "Follow the edit dependency path.")
            if self.map.get("id") == "widget-runtime":
                question += " These are existing functions; choose an edit point by the behavior you want to change."
            self.text(question, 0, self.height - 2, self.width, "question")
            key_w, key_gap = 174, 15
            grid_w = self.width - key_w - key_gap
            key_x = grid_w + key_gap
            nodes = self.map.get("nodes", [])
            numbers = {node["id"]: f"N{index}" for index, node in enumerate(nodes, 1)}
            min_c = min((int(n.get("column", 0)) for n in nodes), default=0)
            min_r = min((int(n.get("row", 0)) for n in nodes), default=0)
            cols = max((int(n.get("column", 0)) - min_c for n in nodes), default=0) + 1
            rows = max((int(n.get("row", 0)) - min_r for n in nodes), default=0) + 1
            grid_top, grid_bottom = self.height - 43, 31
            grid_h = grid_top - grid_bottom
            cell_w, cell_h = grid_w / cols, grid_h / rows
            gap_x, gap_y = 17, 17
            box_w, box_h = cell_w - gap_x, cell_h - gap_y
            placed = {}
            for node in nodes:
                column, row = int(node.get("column", 0)) - min_c, int(node.get("row", 0)) - min_r
                x, y = column * cell_w + gap_x / 2, grid_top - (row + 1) * cell_h + gap_y / 2
                placed[node["id"]] = {"node": node, "column": column, "row": row,
                                      "box": (x, y, box_w, box_h)}
            for index, edge in enumerate(self.map.get("edges", []), 1):
                if edge.get("from") not in placed or edge.get("to") not in placed:
                    continue
                points, badge = self.route(placed[edge["from"]], placed[edge["to"]], index,
                                           cell_w, cell_h, grid_top)
                self.arrow(points, edge, index, badge)
            for data in placed.values():
                node = data["node"]
                x, y, w, h = data["box"]
                role = node.get("role", "EDIT")
                fill, border = role_colors.get(role, role_colors["EDIT"])
                c.setFillColor(fill)
                c.setStrokeColor(border)
                c.setLineWidth(0.9)
                c.setDash(3, 2) if node.get("status") == "proposed" else c.setDash()
                c.roundRect(x, y, w, h, 5, fill=1, stroke=1)
                c.setDash()
                c.linkRect("", _dest("node", self.map["id"], node["id"]),
                           (x, y, x + w, y + h), relative=1)
                top = y + h - 8
                role_label = f"{numbers[node['id']]} | {role}" + (" | PLAN" if role == "NEW" else "")
                c.setFont("Helvetica-Bold", 9)
                c.setFillColor(border)
                c.drawString(x + 7, top - 7, _plain(role_label))
                top -= 19
                title_text = _esc(node.get("title", "")).replace("::", "::<br/>")
                top -= self.text(title_text, x + 7, top, w - 14, "node-title", raw=True) + 5
                path = node.get("path", "")
                primary = primary_reference(node)
                status = primary.get("status", "verified" if path else "missing")
                if status == "missing":
                    location = "REVIEW REQUIRED: source not captured"
                elif role == "NEW":
                    location = ("Existing source/example: " + link(f"{path}:{node.get('line') or 1}", _source_url(primary))) if path else "Planned application addition"
                elif path:
                    location = link(f"{path}:{node.get('line') or 1}", _source_url(primary))
                    if str(path).startswith("@"):
                        location = "Read-only evidence:<br/>" + location
                else:
                    location = "Choose by responsibility"
                if node.get("status") == "missing" and status != "missing":
                    location += "<br/><b>Review related sources</b>"
                location_para = paragraph(location, "node-source", raw=True)
                _, location_h = location_para.wrap(w - 14, h)
                available = top - y - location_h - 14
                action = _plain(node.get("summary") or node.get("action", ""))
                original_action = action
                action_para = paragraph(action, "node-body")
                _, action_h = action_para.wrap(w - 14, h)
                while action and action_h > available:
                    action = action[:-8].rstrip()
                    action_para = paragraph(action + " ...", "node-body")
                    _, action_h = action_para.wrap(w - 14, h)
                if action:
                    action_para.drawOn(c, x + 7, top - action_h)
                elif original_action:
                    self.text("Action in linked details", x + 7, top, w - 14, "node-body")
                location_para.drawOn(c, x + 7, y + 7)
            c.setStrokeColor(rule)
            c.line(key_x - 8, 27, key_x - 8, grid_top + 7)
            key_top = grid_top + 5
            key_top -= self.text("DIRECTED EDGE KEY", key_x, key_top, key_w, "node-title") + 7
            key_top -= self.text(self.map.get("edge_meaning", "Arrows show where to continue the edit."),
                                 key_x, key_top, key_w, "edge-key") + 9
            for index, edge in enumerate(self.map.get("edges", []), 1):
                label = f"<b>{index}. {_esc(numbers.get(edge.get('from'), edge.get('from', '')))} -&gt; {_esc(numbers.get(edge.get('to'), edge.get('to', '')))}</b><br/>{_esc(edge.get('label', 'continue'))}"
                key_top -= self.text(label, key_x, key_top, key_w, "edge-key", raw=True) + 5
            legend_y = 9
            for index, role in enumerate(role_colors):
                x = index * 113
                fill, border = role_colors[role]
                c.setFillColor(fill)
                c.setStrokeColor(border)
                c.roundRect(x, legend_y - 1, 10, 10, 2, fill=1, stroke=1)
                c.setFillColor(ink)
                c.setFont("Helvetica", 9)
                c.drawString(x + 15, legend_y, role)
            c.setFont("Helvetica", 9)
            c.setFillColor(muted)
            c.drawRightString(self.width, legend_y, "Click a card for the edit action")

    def node_details(map_value: dict[str, Any], node: dict[str, Any], number: int) -> list[Any]:
        role, status = node.get("role", "EDIT"), node.get("status", "verified")
        parts = [Heading(f"N{number} | {role} | {node.get('title', '')}",
                         _dest("node", map_value["id"], node["id"]), level=2)]
        if role == "NEW":
            parts.append(paragraph("<b>Planned addition to this application.</b> It is not implemented yet; links show existing source and examples.", "small", raw=True))
        if status == "missing":
            parts.append(paragraph("<b>Review required:</b> one or more source anchors were not captured. Verify the listed targets before editing.", "small", raw=True))
        action = node.get("action") or node.get("summary", "")
        if action:
            parts.append(paragraph("<b>Action:</b> " + _esc(action), raw=True))
        references = []
        if node.get("path") or status in {"missing", "proposed"}:
            references.append(primary_reference(node))
        references.extend(node.get("references", []))
        unique = {}
        for reference in references:
            unique.setdefault((reference.get("path"), reference.get("line")), reference)
        if unique:
            parts.append(paragraph("<br/>".join(ref_text(reference) for reference in unique.values()), "small", raw=True))
        if node.get("link_map"):
            parts.append(paragraph(link("Drill down to the related edit map", "#" + _dest("chart", node["link_map"])), "small", raw=True))
        parts.append(paragraph(link("Up to chart", "#" + _dest("chart", map_value["id"])) + " | " +
                               link("Full rationale in explorer", "../index.html#change/" + quote(map_value["id"], safe="") + "/" + quote(node["id"], safe="")) +
                               " | " + _esc(node["id"]),
                               "small", raw=True))
        return [KeepTogether(parts), Spacer(1, 2)]

    story = []
    doc = EditDoc()
    for index, map_value in enumerate(maps):
        if index:
            # Set the next header before the new page begins. Changing it in
            # the new page's body would leave that page's header on the old map.
            story += [SetMap(map_value), NextPageTemplate("chart"), PageBreak()]
        story += [SetMap(map_value), Chart(map_value), NextPageTemplate("details"), PageBreak(),
                  Heading("Actions behind this path", _dest("details", map_value["id"]), 1, chapter=True),
                  paragraph(map_value.get("summary", "Follow the linked cards to source before making a change."), "small"),
                  paragraph(link("Up to chart", "#" + _dest("chart", map_value["id"])) +
                            " | The path is an editing plan. Runtime arrows are identified in the edge key.",
                            "small", raw=True)]
        for number, node in enumerate(map_value.get("nodes", []), 1):
            story.extend(node_details(map_value, node, number))
    doc.build(story)
    return ["pdf/00-edit-paths.pdf"]
