"""One renderer for the preview, raster export, PDF and printer."""
import base64
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QImageReader, QPageLayout, QPageSize, QPainter, QPdfWriter

from .core import DomainError
from .templates import WIDTH_MM, HEIGHT_MM, validate_template

DPI = 300
WIDTH = round(WIDTH_MM / 25.4 * DPI)
HEIGHT = round(HEIGHT_MM / 25.4 * DPI)


def image_bytes(image):
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise DomainError("Unable to encode image.")
    return bytes(data)


def load_image(path):
    if Path(path).stat().st_size > 20_000_000:
        raise DomainError("Choose an image smaller than 20 MB.")
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if not size.isValid() or size.width() * size.height() > 40_000_000:
        raise DomainError("Image is invalid or exceeds 40 megapixels.")
    image = reader.read()
    if image.isNull():
        raise DomainError("Cannot read this image. Choose PNG or JPEG.")
    return image


def normalize_signature(image):
    """White paper becomes transparent; dark pen marks keep their coverage."""
    if image.width() > 1200 or image.height() > 400:
        image = image.scaled(1200, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    result = image.convertToFormat(QImage.Format.Format_ARGB32)
    ink = False
    for y in range(result.height()):
        for x in range(result.width()):
            c = result.pixelColor(x, y)
            coverage = int((255 - min(c.red(), c.green(), c.blue())) * c.alpha() / 255)
            result.setPixelColor(x, y, QColor(20, 35, 50, coverage))
            ink |= coverage > 30
    if not ink:
        raise DomainError("The signature image contains no visible ink.")
    return result


def page_size():
    return QPageSize(QSizeF(WIDTH_MM, HEIGHT_MM), QPageSize.Unit.Millimeter, "CR80", QPageSize.SizeMatchPolicy.ExactMatch)


def validate_assets(template):
    validate_template(template)
    for side in ("front", "back"):
        raw = template.get(side + "_background")
        if raw:
            image = QImage.fromData(base64.b64decode(raw))
            if image.isNull() or image.width() * image.height() > 40_000_000:
                raise DomainError("Invalid background image.")


def render_card(record, template, side="front", watermark=""):
    validate_assets(template)
    canvas = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("#ffffff"))
    canvas.setDotsPerMeterX(round(DPI / .0254))
    canvas.setDotsPerMeterY(round(DPI / .0254))
    painter = QPainter(canvas)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        sx, sy = WIDTH / WIDTH_MM, HEIGHT / HEIGHT_MM
        background = template.get(side + "_background")
        if background:
            painter.drawImage(QRectF(0, 0, WIDTH, HEIGHT), QImage.fromData(base64.b64decode(background)))
        else:
            painter.fillRect(QRectF(0, 0, WIDTH, 14 * sy), QColor(template["accent"]))
            painter.fillRect(QRectF(0, HEIGHT - 2 * sy, WIDTH, 2 * sy), QColor(template["accent"]))
        for item in template[side]:
            rect = QRectF(item["x"] * sx, item["y"] * sy, item["w"] * sx, item["h"] * sy)
            key = item["key"]
            painter.save()
            painter.setClipRect(rect)
            if key in ("photo", "signature"):
                raw = record.get(key)
                image = QImage.fromData(raw) if raw else QImage()
                if raw and image.isNull():
                    raise DomainError(f"The {key} image is damaged. Import it again before approval.")
                if image.isNull():
                    painter.fillRect(rect, QColor("#e9eef4"))
                    painter.setPen(QColor("#64748b"))
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, key.upper())
                else:
                    mode = Qt.AspectRatioMode.KeepAspectRatioByExpanding if key == "photo" else Qt.AspectRatioMode.KeepAspectRatio
                    scaled = image.scaled(rect.size().toSize(), mode, Qt.TransformationMode.SmoothTransformation)
                    target = QRectF(rect.center().x() - scaled.width()/2, rect.center().y() - scaled.height()/2, scaled.width(), scaled.height())
                    painter.drawImage(target, scaled)
            else:
                text = template["organization"] if key == "organization" else item.get("text", "") if key == "text" else str(record.get(key, ""))
                if key == "expires":
                    text = "Valid to " + text
                font = QFont("Segoe UI")
                pixels = round(item["size"] * DPI / 72)
                font.setBold(key in ("organization", "full_name", "card_no"))
                flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap
                while pixels >= 12:
                    font.setPixelSize(pixels)
                    metrics = QFontMetricsF(font)
                    bounds = metrics.boundingRect(rect, int(flags), text)
                    if bounds.height() <= rect.height() and bounds.width() <= rect.width():
                        break
                    pixels -= 1
                font.setPixelSize(max(12, pixels))
                bounds = QFontMetricsF(font).boundingRect(rect, int(flags), text)
                if bounds.height() > rect.height() + 1 or bounds.width() > rect.width() + 1:
                    raise DomainError(f"The {key.replace('_', ' ')} text does not fit its template field. Shorten it or enlarge that field.")
                painter.setFont(font)
                painter.setPen(QColor(item["color"]))
                painter.drawText(rect, flags, text)
            painter.restore()
        if watermark:
            painter.save()
            painter.translate(WIDTH/2, HEIGHT/2)
            painter.rotate(-22)
            painter.setPen(QColor(170, 40, 55, 125))
            font = QFont("Segoe UI")
            font.setPixelSize(80)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(-WIDTH/2, -80, WIDTH, 160), Qt.AlignmentFlag.AlignCenter, watermark)
            painter.restore()
    finally:
        painter.end()
    return canvas


def export_pdf(path, images):
    writer = QPdfWriter(str(path))
    writer.setResolution(DPI)
    writer.setPageLayout(QPageLayout(page_size(), QPageLayout.Orientation.Portrait, QMarginsF(0,0,0,0), QPageLayout.Unit.Millimeter))
    writer.setTitle("Credential Studio — CR80 card")
    painter = QPainter()
    if not painter.begin(writer):
        raise DomainError("Cannot create PDF at this location.")
    try:
        for index, image in enumerate(images):
            if index and not writer.newPage():
                raise DomainError("Cannot create PDF page.")
            painter.drawImage(QRectF(0, 0, writer.width(), writer.height()), image)
    finally:
        painter.end()
