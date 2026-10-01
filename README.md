# Credential Studio

**A focused Windows workstation for professional identity card enrollment, design and issuance.**

Credential Studio brings cardholder details, camera portraits, handwritten signatures, card templates and printer output into one local workspace. Built for staff, school, membership and visitor credential programs, it helps an operator move from enrollment to a reviewed, traceable card without switching between design software, image editors and spreadsheets.

**Status: v0.1.0 — functional pilot implementation.** This repository contains a working desktop application, automated tests, Windows packaging and a customer handover guide. It is not yet a hardware-certified or production-accredited release. Use the [acceptance checklist](docs/ACCEPTANCE.md) before selling a deployment as production ready.

## What you can do

| Workspace | Capabilities |
|---|---|
| Overview | Live local counts, recent enrollments, unresolved print jobs |
| Cardholders | Search name/card number, filter by status, open records, administrator CSV export |
| Enrollment | Required-field checks, duplicate ID protection, expiry dates, photo import, live camera capture, drag/zoom portrait framing |
| Signatures | Draw with mouse/touch/pen, import a signature image, capture through the Windows Wacom COM adapter |
| Template studio | Two starter designs, organization branding, front/back layouts, custom image backgrounds, millimeter position/size controls, live preview, JSON import/export |
| Review & issuance | Administrator approval, draft watermarking, revision protection, revocation and reasoned reprints |
| Printing | Discover installed printers, select front/back/automatic duplex, validate CR80 form, submit through the native Qt/Windows driver stack |
| Print history | Immutable rendered snapshots, submitted/uncertain/confirmed states, physical-output confirmation, interruption recovery without automatic reprinting |
| Administration | First-run administrator setup, operator accounts, password change, account disabling, audit history, idle lock, full backup and safe restore |

## Operator workflow

1. Install the Windows setup package and create the first administrator account.
2. Open **Template studio**, adapt the organization and layout, then save.
3. Select **Enroll cardholder**. Enter the name, unique card number, role and expiry.
4. Import a portrait or use the camera. Drag and zoom to frame the face.
5. Capture or import the signature and record capture authorization.
6. Check front and back; choose **Save draft**.
7. An administrator reviews the card and chooses **Approve card**.
8. Choose **Print card**, the installed printer and required sides.
9. Inspect the physical output. In **Print history**, choose **Confirm printed** only when the requested output is correct.

Shortcuts: **Ctrl+N** new enrollment, **Ctrl+S** save enrollment, **Ctrl+L** lock. Unsaved work is retained while the same operator unlocks. Close and reopen the application to switch operator accounts.

## Windows installer

The [Windows build workflow](https://github.com/birleopold/ID-Issuance-System-/actions/workflows/windows.yml) tests the app, bundles the Python runtime and Qt libraries, builds an Inno Setup installer, and smoke-tests installation, launch and removal. After a successful run, download the **CredentialStudio-Windows-x64** artifact and extract the setup executable. A configured workflow is not proof that a run passed; inspect the run status.

The client does **not** need Python, pip, a terminal or development libraries. The installer installs per Windows user, creates shortcuts and preserves the data folder during uninstall. The initial build is unsigned; code signing and hardware qualification are release gates.

Hardware still requires compatible Windows drivers. Wacom requires its licensed Signature SDK and appropriate bitness; this proprietary software is not included. The deployment technician must provision the selected devices and SDK before handover. The application never pretends that an unavailable device is connected.

## Development

Windows 10/11 x64 is the deployment target. Python 3.12 x64 is the reference build runtime.

```powershell
git clone https://github.com/birleopold/ID-Issuance-System-.git
cd ID-Issuance-System-
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[dev]"
.\.venv\Scripts\python.exe run.py
```

Build a client installer on Windows with Inno Setup 6 installed:

```powershell
.\packaging\build.ps1
```

Development tests (Qt offscreen is suitable for CI):

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:QT_QPA_PLATFORM
```

## Architecture

- **Python + PySide6:** native desktop UI, camera via Qt Multimedia, common renderer for preview/export/printing.
- **SQLite:** transactional local persistence with foreign keys, WAL journaling, schema versioning and consistent backups. No network or cloud dependency.
- **Service layer:** authorization enforced independently of enabled/disabled buttons; optimistic record versions prevent lost updates.
- **Issuance lifecycle:** `draft → approved → issued → revoked`. Only drafts are editable. An approved card may return to draft with an administrator reason when there is no unresolved print job.
- **Hardware adapters:** printer driver integration and Wacom COM capture, with explicit failures and no success simulation.
- **Distribution:** PyInstaller onedir package + Inno Setup + Windows CI.

## Scope and limits

This is a **single-workstation, single-Windows-profile** product. Operator accounts are application accounts within that profile; independent Windows profiles have independent default data. Do not place the SQLite database on a network share. Multi-site synchronization, central identity services, bulk issuance, smart-card encoding, holographic security, online verification, automatic updates, licensing/billing and encrypted application databases are not implemented.

Records and backups contain sensitive personal data. Passwords use salted scrypt; the database itself is **not encrypted**. The audit table rejects ordinary SQL edits, but it is not tamper-proof against someone with filesystem or database-administrator access. Protect the Windows profile and storage. A captured signature is an image for card production, not a cryptographic digital signature or identity-verification guarantee. Revocation records the credential as revoked locally; it cannot disable a physical card or an unrelated access-control system.

CR80 is modeled as **85.60 × 53.98 mm**. At 300 DPI the rounded raster is **1011 × 638 pixels**; physical page dimensions control PDF and printer output. Driver calibration, printable margins, duplex alignment and color must be tested on the chosen printer.

## Documentation

- [Product description and usability](docs/PRODUCT.md)
- [Operator guide and recovery](docs/OPERATIONS.md)
- [Hardware integration and technical references](docs/HARDWARE.md)
- [Production acceptance checklist](docs/ACCEPTANCE.md)
- [Security and data model](docs/SECURITY.md)
- [Third-party distribution notes](docs/THIRD_PARTY.md)

No application redistribution license has been selected in this repository. The owner should choose commercial terms before distribution; third-party components retain their own terms.
