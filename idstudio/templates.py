"""Portable, data-only templates. No executable expressions or remote assets."""
import base64
import copy
import math
import re

from .core import DomainError

WIDTH_MM, HEIGHT_MM = 85.60, 53.98
FIELDS = ("organization", "full_name", "card_no", "department", "title", "expires", "photo", "signature", "text")


def field(key, x, y, w, h, size=10, color="#142b46", text=""):
    return dict(key=key, x=x, y=y, w=w, h=h, size=size, color=color, text=text)


def default_templates():
    corporate = {
        "version": 1, "organization": "YOUR ORGANIZATION", "accent": "#155e75",
        "front_background": "", "back_background": "",
        "front": [field("organization", 5, 4, 75, 7, 11, "#ffffff"),
                  field("photo", 5, 17, 22, 29),
                  field("full_name", 31, 18, 49, 9, 14),
                  field("title", 31, 28, 49, 5, 9),
                  field("department", 31, 34, 49, 5, 9),
                  field("card_no", 31, 41, 49, 5, 11),
                  field("text", 5, 49, 75, 3, 6, "#52677b", "OFFICIAL STAFF CREDENTIAL")],
        "back": [field("organization", 5, 4, 75, 7, 11, "#ffffff"),
                 field("text", 5, 18, 75, 12, 9, text="This card remains the property of the issuing organization. If found, please return it to reception."),
                 field("signature", 5, 33, 38, 10),
                 field("text", 5, 44, 38, 4, 6, text="HOLDER SIGNATURE"),
                 field("expires", 48, 35, 32, 6, 9),
                 field("card_no", 48, 43, 32, 5, 9)]}
    campus = copy.deepcopy(corporate)
    campus["accent"] = "#5741a3"
    campus["front"][-1]["text"] = "STUDENT & CAMPUS SERVICES"
    return {"Corporate / Ocean": corporate, "Campus / Iris": campus}


def validate_template(body):
    if not isinstance(body, dict) or body.get("version") != 1:
        raise DomainError("Unsupported template format. Expected version 1.")
    if not isinstance(body.get("organization"), str) or not 1 <= len(body["organization"]) <= 100:
        raise DomainError("Organization must contain 1–100 characters.")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(body.get("accent", ""))):
        raise DomainError("Accent must be a six-digit hex color, e.g. #155e75.")
    for side in ("front", "back"):
        fields = body.get(side)
        if not isinstance(fields, list) or not 1 <= len(fields) <= 30:
            raise DomainError("Each side must contain 1–30 fields.")
        bg = body.get(side + "_background", "")
        if not isinstance(bg, str) or len(bg) > 12_000_000:
            raise DomainError("Background image is too large.")
        if bg:
            try:
                base64.b64decode(bg, validate=True)
            except Exception as exc:
                raise DomainError("Invalid background encoding.") from exc
        for item in fields:
            if not isinstance(item, dict) or item.get("key") not in FIELDS:
                raise DomainError("Unsupported field type.")
            for prop in ("x", "y", "w", "h", "size"):
                v = item.get(prop)
                if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
                    raise DomainError("Field coordinates and size must be finite numbers.")
            if item["x"] < 0 or item["y"] < 0 or item["w"] <= 0 or item["h"] <= 0:
                raise DomainError("Field positions must be positive and dimensions nonzero.")
            if item["x"] + item["w"] > WIDTH_MM + 0.001 or item["y"] + item["h"] > HEIGHT_MM + 0.001:
                raise DomainError("A field extends beyond the card boundary.")
            if not 4 <= item["size"] <= 48:
                raise DomainError("Font size must be between 4 and 48 points.")
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(item.get("color", ""))):
                raise DomainError("Field colors must be six-digit hex colors.")
            if not isinstance(item.get("text", ""), str) or len(item.get("text", "")) > 500:
                raise DomainError("Static text must be at most 500 characters.")
