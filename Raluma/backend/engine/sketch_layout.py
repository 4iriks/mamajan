"""Fit each sketch product using measured text, without dropping document rows."""

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class SketchLayout:
    scale: float = 1.0
    compact: bool = False

    @property
    def spacing(self):
        return self.scale * (0.55 if self.compact else 1.0)

    @property
    def line_height(self):
        return 1.05 if self.compact else 1.15

    def diagram_height(self, kind):
        return self.scale * (
            (65 if self.compact else 75)
            if kind == "room"
            else (23 if self.compact else 27)
        )


def layout_css(layouts):
    rules = []
    for index, fit in enumerate(layouts):
        prefix = f'.sketch-section[data-sketch-index="{index}"]'

        def rule(selectors, properties):
            selector = ",".join(prefix + (" " + s if s else "") for s in selectors)
            rules.append(
                selector
                + "{"
                + ";".join(f"{k}:{v} !important" for k, v in properties.items())
                + "}"
            )

        def mm(value):
            return f"{value * fit.spacing:.4f}mm"

        def pt(value):
            return f"{value * fit.scale:.4f}pt"

        rule(
            [""],
            {
                "font-size": pt(9.5),
                "line-height": str(fit.line_height),
                "margin-bottom": "0",
                "break-inside": "avoid",
            },
        )
        rule(
            ["table", ".panel-table td:nth-child(4)", ".panel-table td:nth-child(5)"],
            {"font-size": pt(9.5)},
        )
        rule(
            ["th", "td"],
            {
                "padding": f"{mm(0.9)} {mm(1.4)}",
                "border-width": f"{0.25 * fit.scale:.4f}mm",
            },
        )
        rule([".meta-grid", ".meta-label"], {"font-size": pt(10)})
        rule([".meta-item"], {"padding": f"{mm(1)} {mm(1.7)}"})
        rule(
            [".section-heading"],
            {
                "font-size": pt(11),
                "margin-bottom": mm(2.5),
                "padding": f"{mm(2)} {mm(2.4)}",
            },
        )
        rule([".meta-grid", ".diagram-grid"], {"margin-bottom": mm(2.5)})
        rule([".diagram-grid"], {"gap": mm(2.5)})
        rule([".diagram"], {"padding": mm(1.5), "min-height": "0"})
        rule([".diagram-title"], {"font-size": pt(7), "margin-bottom": mm(1)})
        for kind in ("room", "top"):
            rule(
                [f".diagram-{kind} img"],
                {"height": f"{fit.diagram_height(kind):.4f}mm"},
            )
        rule(
            [".section-comment"],
            {
                "font-size": pt(7.5),
                "margin-bottom": mm(2.5),
                "padding": f"{mm(1.5)} {mm(2)}",
            },
        )
        rule(
            [".table-title"], {"font-size": pt(9.5), "margin": f"{mm(2.5)} 0 {mm(1.2)}"}
        )
    return "\n".join(rules)


@lru_cache(maxsize=16)
def _fit_html(html, count):
    from weasyprint import CSS, HTML

    if not count:
        return ()
    layouts = [SketchLayout() for _ in range(count)]
    # Measure unsplit content with the same renderer, width and fonts as the PDF.
    measure = CSS(
        string="@page { size: 210mm 2000mm !important; margin: 10mm 11mm 12mm !important; }"
    )
    for _ in range(12):
        document = HTML(string=html).render(
            stylesheets=[measure, CSS(string=layout_css(layouts))]
        )
        heights = [0.0] * count
        title_height = 0.0
        for page in document.pages:
            for box in page._page_box.descendants():
                if type(box).__name__ != "BlockBox" or box.element is None:
                    continue
                index = box.element.get("data-sketch-index")
                if index is not None:
                    heights[int(index)] += box.margin_height() * 25.4 / 96
                elif box.element.tag == "h1":
                    title_height += box.margin_height() * 25.4 / 96
        changed = False
        for index, height in enumerate(heights):
            # Six mm reserve also covers editable Word table/paragraph rounding.
            available = 269 - (title_height if index == 0 else 0)
            if height <= available:
                continue
            fit = layouts[index]
            layouts[index] = (
                SketchLayout(compact=True)
                if not fit.compact
                else SketchLayout(
                    scale=fit.scale * min(0.97, available / height * 0.98), compact=True
                )
            )
            changed = True
        if not changed:
            return tuple(layouts)
    raise ValueError(
        "Не удалось разместить изделие на одной странице эскизного проекта"
    )


def fit_sketch_context(context, template=None):
    if template is None:
        from engine.project_documents import _get_env

        template = _get_env().get_template("sketch_project.html")
    measurement = {**context, "project_components": [], "sketch_fit_css": ""}
    layouts = _fit_html(template.render(**measurement), len(context["sections"]))
    context["sketch_layouts"] = layouts
    context["sketch_fit_css"] = layout_css(layouts)
    return layouts
