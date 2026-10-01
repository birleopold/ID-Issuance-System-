"""Real hardware boundaries. Never report a simulated device as connected."""
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QImage, QPageLayout, QPainter
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

from .core import DomainError
from .rendering import HEIGHT_MM, WIDTH_MM, normalize_signature, page_size


def printer_names():
    return [p.printerName() for p in QPrinterInfo.availablePrinters()]


def configured_printer(name, duplex):
    if name not in printer_names():
        raise DomainError("Selected printer is unavailable. Check the connection and Windows driver.")
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPrinterName(name)
    printer.setResolution(300)
    printer.setCopyCount(1)
    printer.setFullPage(True)
    layout = QPageLayout(page_size(), QPageLayout.Orientation.Portrait, QMarginsF(0,0,0,0), QPageLayout.Unit.Millimeter)
    if not printer.setPageLayout(layout):
        raise DomainError("Printer rejected CR80 size. Configure a custom 85.60 × 53.98 mm form in its driver.")
    actual = printer.pageLayout().fullRect(QPageLayout.Unit.Millimeter)
    if abs(actual.width() - WIDTH_MM) > .6 or abs(actual.height() - HEIGHT_MM) > .6:
        raise DomainError("Printer substituted another paper size. Set CR80 in its driver and retry.")
    printer.setDuplex(QPrinter.DuplexMode.DuplexShortSide if duplex else QPrinter.DuplexMode.DuplexNone)
    if duplex and printer.duplex() == QPrinter.DuplexMode.DuplexNone:
        raise DomainError("Driver did not accept duplex printing. Use front-only mode or a duplex-capable printer.")
    if not printer.isValid():
        raise DomainError("Printer is not ready.")
    return printer


def submit_print(printer, images, job_id):
    printer.setDocName("Credential Studio " + job_id)
    painter = QPainter()
    if not painter.begin(printer):
        raise DomainError("Windows did not start the print job. Inspect its queue before retrying.")
    try:
        target = printer.paperRect(QPrinter.Unit.DevicePixel)
        for index, image in enumerate(images):
            if index and not printer.newPage():
                raise DomainError("Printer could not start the reverse side. Check physical output before retrying.")
            painter.drawImage(QRectF(target), image)
    except Exception:
        printer.abort()
        raise
    finally:
        ended = painter.end()
    if not ended or printer.printerState() in (QPrinter.PrinterState.Error, QPrinter.PrinterState.Aborted):
        raise DomainError("Print submission was interrupted. Inspect physical output and the queue.")


def capture_wacom(who):
    """Wacom Ink SDK for signature COM adapter; matching SDK bitness required."""
    if sys.platform != "win32":
        raise DomainError("Wacom capture requires Windows and the licensed Wacom Signature SDK.")
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise DomainError("The Windows hardware component is missing from this build.") from exc
    pythoncom.CoInitialize()
    try:
        sig = win32com.client.Dispatch("Florentis.SigCtl")
        license_value = os.environ.get("CREDENTIAL_STUDIO_WACOM_LICENSE")
        if license_value:
            sig.Licence = license_value
        capture = win32com.client.Dispatch("Florentis.DynamicCapture")
        result = capture.Capture(sig, who, "Identity card issuance")
        if result == 1:
            raise DomainError("Signature capture was cancelled.")
        if result != 0:
            raise DomainError(f"Wacom capture failed (SDK result {result}). Check the pad, driver and SDK licence.")
        with tempfile.TemporaryDirectory() as folder:
            target = str(Path(folder) / "signature.png")
            # RenderOutputFilename | RenderColor32BPP | RenderColorAntiAlias.
            sig.Signature.RenderBitmap(target, 900, 300, "image/png", .7, 0x000000, 0xFFFFFF, 0, 0, 0x1000 | 0x80000 | 0x100000)
            image = QImage(target)
            if image.isNull():
                raise DomainError("Wacom returned no signature image.")
            return normalize_signature(image)
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError("Wacom SDK unavailable. Install and activate the matching 64-bit Signature SDK and pad driver, then run the vendor capture sample.") from exc
    finally:
        pythoncom.CoUninitialize()
