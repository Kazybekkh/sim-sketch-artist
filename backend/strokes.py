"""Bounded page coordinates, pen-travel ordering, and raster previews."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Annotated, Any

from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

MAX_STROKES = 40
MAX_POINTS = 25
Coordinate = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Point = Annotated[list[Coordinate], Field(min_length=2, max_length=2)]
Stroke = Annotated[list[Point], Field(min_length=2, max_length=MAX_POINTS)]


class Drawing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    strokes: Annotated[list[Stroke], Field(min_length=1, max_length=MAX_STROKES)]

    @field_validator("strokes", mode="before")
    @classmethod
    def numeric_coordinates(cls, value: Any) -> Any:
        # Pydantic otherwise accepts booleans and numeric strings as floats.
        if not isinstance(value, list):
            raise ValueError("strokes must be an array")
        for stroke in value:
            if not isinstance(stroke, list):
                raise ValueError("each stroke must be an array")
            for point in stroke:
                if not isinstance(point, list) or len(point) != 2:
                    raise ValueError("each point must be [x, y]")
                if any(type(coordinate) not in (int, float) for coordinate in point):
                    raise ValueError("coordinates must be numbers")
        return value


def clean_model_drawing(value: Any) -> Drawing:
    """Repair bounded model output; API /draw remains strictly validated."""
    if not isinstance(value, dict) or not isinstance(value.get("strokes"), list):
        raise ValueError("model output must contain a strokes array")
    strokes = []
    for candidate in value["strokes"]:
        if not isinstance(candidate, list):
            continue
        points = []
        for point in candidate:
            if not isinstance(point, list) or len(point) != 2:
                continue
            if any(type(c) not in (int, float) for c in point):
                continue
            try:
                pair = [float(c) for c in point]
            except (ValueError, OverflowError):
                continue
            if not all(math.isfinite(c) for c in pair):
                continue
            pair = [max(0.0, min(1.0, c)) for c in pair]
            if not points or pair != points[-1]:
                points.append(pair)
            if len(points) == MAX_POINTS:
                break
        if len(points) >= 2:
            strokes.append(points)
        if len(strokes) == MAX_STROKES:
            break
    title = value.get("title")
    title = title.strip()[:120] if isinstance(title, str) else "Line portrait"
    return Drawing(title=title or "Line portrait", strokes=strokes)


def order_strokes(drawing: Drawing) -> Drawing:
    """Greedily choose the nearest endpoint; reverse strokes when useful."""
    remaining = [[list(point) for point in stroke] for stroke in drawing.strokes]
    ordered = []
    current = [0.0, 0.0]
    while remaining:
        choices = (
            (math.dist(current, stroke[-1] if reverse else stroke[0]), i, reverse)
            for i, stroke in enumerate(remaining)
            for reverse in (False, True)
        )
        _, index, reverse = min(choices)
        stroke = remaining.pop(index)
        if reverse:
            stroke.reverse()
        ordered.append(stroke)
        current = stroke[-1]
    return Drawing(title=drawing.title, strokes=ordered)


def render_preview(strokes: list, destination: Path, *, size: int = 1024) -> None:
    """Render normalized page coordinates. Also accepts dense simulator trails."""
    scale = 2
    canvas = Image.new("RGB", (size * scale, size * scale), "white")
    pen = ImageDraw.Draw(canvas)
    for stroke in strokes:
        points = [(float(x) * (size - 1) * scale, float(y) * (size - 1) * scale) for x, y in stroke]
        if len(points) >= 2:
            pen.line(points, fill="#202322", width=3 * scale, joint="curve")
    canvas = canvas.resize((size, size), Image.Resampling.LANCZOS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, format="PNG")
