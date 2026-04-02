from __future__ import annotations

import base64
import io
import random
import string
from dataclasses import dataclass
from typing import Final

CAPTCHA_LENGTH: Final = 4
CAPTCHA_WIDTH: Final = 120
CAPTCHA_HEIGHT: Final = 40


@dataclass
class CaptchaResult:
    image_base64: str
    answer: str


def _generate_text(length: int = CAPTCHA_LENGTH) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def _generate_noise_line(width: int, height: int) -> str:
    x1 = random.randint(0, width)
    y1 = random.randint(0, height)
    x2 = random.randint(0, width)
    y2 = random.randint(0, height)
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#cccccc" stroke-width="1"/>'


def _create_svg_image(text: str) -> bytes:
    lines = [_generate_noise_line(CAPTCHA_WIDTH, CAPTCHA_HEIGHT) for _ in range(30)]
    chars_html = ""
    x = 15
    for char in text:
        y = random.randint(25, 35)
        chars_html += f'<text x="{x}" y="{y}" font-size="28" fill="#333333">{char}</text>'
        x += 25

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{CAPTCHA_WIDTH}" height="{CAPTCHA_HEIGHT}">
        <rect width="100%" height="100%" fill="white"/>
        {"".join(lines)}
        {chars_html}
    </svg>'''
    return svg.encode()


def generate_captcha() -> CaptchaResult:
    text = _generate_text()
    svg_bytes = _create_svg_image(text)
    b64 = base64.b64encode(svg_bytes).decode()
    return CaptchaResult(
        image_base64=f"data:image/svg+xml;base64,{b64}",
        answer=text,
    )
