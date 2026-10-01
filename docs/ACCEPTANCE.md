# Production acceptance gates

The application can be evaluated as a pilot. Do not label a customer installation industrial-grade solely because the code compiles or unit tests pass. Record the tester, date, Windows image, devices, versions and outcomes for the following gates.

## Build and distribution

- [ ] Windows CI passes all tests and produces the installer artifact.
- [ ] Install on a clean supported Windows x64 machine with no Python/development dependencies installed.
- [ ] Launch from Start and desktop shortcuts, including a Windows username containing spaces and non-ASCII characters.
- [ ] First-run account creation, relaunch, upgrade, uninstall and preserved data verified.
- [ ] Sign application/installer with the vendor’s chosen code-signing certificate and timestamp; verify signatures and SmartScreen behavior.
- [ ] Review application commercial terms and all third-party notices/redistribution obligations.

## Workflow and accessibility

- [ ] Real operator completes enrollment, edit, approval, export, print and outcome confirmation without development assistance.
- [ ] Check 100%, 125%, 150% and 200% Windows scaling; keyboard navigation and minimum screen size.
- [ ] Verify long names, non-Latin names and required organizational languages/fonts fit printed output.
- [ ] Save/restore behavior, idle lock, expired cards, duplicate numbers and disabled accounts exercised.
- [ ] Confirm administrator/operator responsibilities and whether independent approval is required.

## Hardware

- [ ] Selected camera permission, capture, disconnect/reconnect and portrait quality validated.
- [ ] Selected signature pad, driver, licensed SDK and x64 COM registration verified using vendor sample and this application.
- [ ] Wacom cancellation, unplug, missing licence and invalid-device behavior exercised.
- [ ] Printer accepts actual CR80 stock with correct color, orientation, scale and printable margins.
- [ ] Automatic duplex alignment and flip direction verified if sold as part of the solution.
- [ ] Offline printer, jam, ribbon depletion, Windows queue cancellation and crash after submission tested.
- [ ] No duplicate physical card is produced by recovery/retry procedures.

## Durability, privacy and operations

- [ ] Complete backup and restore drill on a second local folder/PC using only the backup and documented credentials.
- [ ] Agree on encryption, access control, retention, deletion and incident response with the customer.
- [ ] Protect and restrict unencrypted backup and export locations.
- [ ] Establish target record count and daily throughput; test representative volumes, media sizes and disk-full behavior.
- [ ] Confirm database backups include all media and historical output.
- [ ] Establish support contacts, service terms, spare stock/ribbons, recovery responsibilities and update procedure.
- [ ] Customer signs off on printed samples and the accepted feature/limitation list.

Automated tests cover application logic and Qt rendering. They do not certify the camera, pad, physical printer, security of the Windows deployment or commercial readiness.
