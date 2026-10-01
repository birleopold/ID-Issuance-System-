# Hardware integration

## Camera

Qt Multimedia enumerates available video inputs and captures an image without writing a temporary photograph to disk. A crop/zoom dialog follows capture. Windows camera permissions and any device driver must allow the application to use the camera. No camera is simulated; the import-photo path remains usable when no device is connected. The camera is stopped when its dialog closes.

## Wacom

`idstudio/devices.py` uses the **Wacom Ink SDK for signature COM API**, not an invented direct call to an STU DLL. The adapter creates `Florentis.SigCtl` and `Florentis.DynamicCapture`, invokes `Capture`, checks the result and renders the captured signature to PNG using documented flags. It then normalizes the signature background and stores only the resulting image. It does not preserve the proprietary biometric signature object or claim legally qualified digital signing.

Provision the chosen pad’s supported driver and the matching **64-bit** Wacom Signature SDK on the deployment PC. Verify SDK licensing and run the vendor’s capture sample first. The optional environment variable `CREDENTIAL_STUDIO_WACOM_LICENSE` supplies `SigCtl.Licence`; production provisioning may instead use vendor-supported licensing configuration. Do not commit licence keys. The installer does not redistribute proprietary Wacom packages or keys.

The adapter is implemented against the documented COM surface but has not been executed on a connected Wacom pad in this development environment. Compatibility with STU models, firmware, encryption settings and the purchased SDK edition is a release test, not an assumption. Hardware purchasing should follow a successful integration trial with the vendor.

## Card printer

Qt Print Support discovers Windows-installed printers. A selected printer receives a custom 85.60 × 53.98 mm page, a 300 DPI request and one copy through its native driver. The software checks the accepted page geometry before submission. It paints the same raster used for preview and PDF export. No hardware-specific RAW/ESC/P or spooler byte commands are guessed.

Automatic duplex requests short-edge duplex and checks that the driver did not refuse it. Some drivers expose incomplete capability/state information. Physically verify orientation, scaling, margins, edge coverage, color, ribbon handling, card stock and recovery behavior. The driver may apply settings of its own. A successful painter submission means only that the application handed output to the driver; the operator must inspect the physical card.

This implementation stores an application job UUID in the print document name. It does not track a native Windows spooler job ID or guarantee physical output from a spooler status. Jams, offline devices and queue cancellation are resolved through visible print history and operator confirmation.

## Official references consulted

- [Qt for Python](https://doc.qt.io/qtforpython-6/)
- [Qt deployment with PyInstaller](https://doc.qt.io/qtforpython-6.10/deployment/deployment-pyinstaller.html)
- [QPrinter geometry and state API](https://doc.qt.io/qt-6/qprinter.html)
- [QPageSize exact matching](https://doc.qt.io/qt-6/qpagesize.html)
- [Wacom Signature SDK usage](https://developer-docs.wacom.com/docs/sdk-for-signature/windows/signature-usage/)
- [Wacom DynamicCapture](https://developer-docs.wacom.com/docs/api/com-api/flsigcapt/classes/dynamiccapture/)
- [Wacom bitmap flags](https://developer-docs.wacom.com/docs/api/com-api/flsigcom/enums/)

References guide implementation; they do not substitute for testing the actual deployment hardware.
