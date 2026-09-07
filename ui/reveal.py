"""Generate the animated perimeter highlight used during item reveal."""

import io
import math
from functools import lru_cache

from PIL import Image, ImageDraw


REVEAL_COVER_DURATION_MS = 500
REVEAL_COVER_DELAY_MS = 50
REVEAL_COVER_EDGE = 10
REVEAL_GRADIENT_OVERSHOOT_RATIO = 0.5
REVEAL_DURATION_MS = 500
REVEAL_FADE_MS = 200
REVEAL_FRAME_COUNT = 25
REVEAL_FINAL_HOLD_FRAMES = 2
REVEAL_TAIL_PROGRESS = 0.25
REVEAL_STROKE_WIDTH = 2
SUPERSAMPLE = 3


def _rounded_rect_points(size, radius, samples=720):
    """Return clockwise perimeter points beginning at the top-left tangent."""
    inset = REVEAL_STROKE_WIDTH / 2
    left, top = inset, inset
    right, bottom = size - inset, size - inset
    radius = max(0, min(radius - inset, (right - left) / 2))

    segments = [
        ("line", (left + radius, top), (right - radius, top)),
        ("arc", (right - radius, top + radius), -90, 0),
        ("line", (right, top + radius), (right, bottom - radius)),
        ("arc", (right - radius, bottom - radius), 0, 90),
        ("line", (right - radius, bottom), (left + radius, bottom)),
        ("arc", (left + radius, bottom - radius), 90, 180),
        ("line", (left, bottom - radius), (left, top + radius)),
        ("arc", (left + radius, top + radius), 180, 270),
    ]

    dense = []
    for segment in segments:
        if segment[0] == "line":
            _, start, end = segment
            length = math.dist(start, end)
            count = max(2, round(length * 2))
            dense.extend(
                (
                    start[0] + (end[0] - start[0]) * index / count,
                    start[1] + (end[1] - start[1]) * index / count,
                )
                for index in range(count)
            )
        else:
            _, center, start_angle, end_angle = segment
            arc_length = radius * math.radians(end_angle - start_angle)
            count = max(2, round(arc_length * 2))
            for index in range(count):
                angle = math.radians(
                    start_angle + (end_angle - start_angle) * index / count
                )
                dense.append(
                    (
                        center[0] + radius * math.cos(angle),
                        center[1] + radius * math.sin(angle),
                    )
                )

    # Close the path explicitly so the head finishes exactly where it began.
    dense.append(dense[0])

    # Resample by index to keep animation work bounded and deterministic.
    return [dense[round(i * (len(dense) - 1) / (samples - 1))] for i in range(samples)]


def _trail_color(progress):
    """Interpolate transparent purple -> purple -> cyan -> white."""
    stops = (
        (0.0, (192, 132, 252, 0)),
        (0.18, (192, 132, 252, 235)),
        (0.70, (103, 232, 249, 255)),
        (1.0, (255, 255, 255, 255)),
    )
    for (left_at, left), (right_at, right) in zip(stops, stops[1:]):
        if progress <= right_at:
            amount = (progress - left_at) / (right_at - left_at)
            return tuple(
                round(a + (b - a) * amount) for a, b in zip(left, right)
            )
    return stops[-1][1]


def _cover_trail_color(progress):
    """Interpolate dark purple -> pronounced cyan -> white for the wipe."""
    stops = (
        (0.0, (126, 68, 190, 0)),
        (0.18, (126, 68, 190, 235)),
        (0.70, (103, 232, 249, 255)),
        (1.0, (255, 255, 255, 255)),
    )
    for (left_at, left), (right_at, right) in zip(stops, stops[1:]):
        if progress <= right_at:
            amount = (progress - left_at) / (right_at - left_at)
            return tuple(
                round(a + (b - a) * amount) for a, b in zip(left, right)
            )
    return stops[-1][1]


@lru_cache(maxsize=4)
def reveal_cover_webp(size):
    """Return a transparent white-to-purple wipe with a slower trailing edge."""
    scale = SUPERSAMPLE
    scaled_size = size * scale
    frames = []
    for frame_index in range(REVEAL_FRAME_COUNT):
        elapsed = frame_index / (REVEAL_FRAME_COUNT - 1)
        head = 1 - (1 - elapsed) ** 3  # fast white leading edge
        tail = elapsed * elapsed * (3 - 2 * elapsed)  # slower smooth tail
        head_x = head * scaled_size * (1 + REVEAL_GRADIENT_OVERSHOOT_RATIO)
        tail_x = tail * scaled_size

        frame = Image.new("RGBA", (scaled_size, scaled_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(frame)
        for x in range(scaled_size):
            if x > head_x:
                continue
            elif x < tail_x:
                continue
            elif head_x == tail_x:
                color = (255, 255, 255, 255)
            else:
                color = _cover_trail_color((x - tail_x) / (head_x - tail_x))
            draw.line((x, 0, x, scaled_size), fill=color)

        frames.append(frame.resize((size, size), Image.Resampling.LANCZOS))

    output = io.BytesIO()
    frames[0].save(
        output,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=REVEAL_COVER_DURATION_MS // REVEAL_FRAME_COUNT,
        loop=1,
        lossless=True,
        method=4,
    )
    return output.getvalue()


@lru_cache(maxsize=8)
def reveal_border_webp(size, radius):
    """Return a transparent one-shot-looking WebP perimeter animation."""
    points = _rounded_rect_points(size, radius)
    scale = SUPERSAMPLE
    frames = []
    for frame_index in range(REVEAL_FRAME_COUNT):
        moving_frames = REVEAL_FRAME_COUNT - REVEAL_FINAL_HOLD_FRAMES
        elapsed = min(frame_index / (moving_frames - 1), 1)
        head = elapsed
        tail = elapsed * REVEAL_TAIL_PROGRESS
        start = round(tail * (len(points) - 1))
        end = round(head * (len(points) - 1))

        frame = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(frame)
        if end > start:
            trail_length = end - start
            for point_index in range(start, end):
                progress = (point_index - start + 1) / trail_length
                first = points[point_index]
                second = points[min(point_index + 1, len(points) - 1)]
                draw.line(
                    tuple(value * scale for point in (first, second) for value in point),
                    fill=_trail_color(progress),
                    width=REVEAL_STROKE_WIDTH * scale,
                )
        frames.append(
            frame.resize((size, size), Image.Resampling.LANCZOS)
        )

    output = io.BytesIO()
    frames[0].save(
        output,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=REVEAL_DURATION_MS // REVEAL_FRAME_COUNT,
        loop=1,
        lossless=True,
        method=4,
    )
    return output.getvalue()
