# Operator and administrator guide

## First installation

Run the setup executable. Launch Credential Studio from Start. Create the first administrator with a password of at least 12 characters and store it in the organization’s password manager. There is no default password or hidden recovery account. An administrator can create other operators in Administration.

The default database is `%LOCALAPPDATA%\CredentialStudio\studio.db`. Photographs, signatures, templates, print snapshots and accounts are stored inside it. Do not delete the database, `-wal` or `-shm` files while the application is open. The installer does not overwrite this folder, and uninstall does not delete it.

## Branding and templates

Open Template studio, select a starter and choose Create from selected. Name the organization, choose a six-digit accent color and configure each side. Field coordinates are millimeters from the top-left corner; font sizes are points. Importing a background stretches it to the card aspect ratio, so prepare artwork at 85.60:53.98 to avoid distortion. Imported backgrounds replace the built-in header and footer; choose text colors that contrast with the artwork. Keep critical content at least a few millimeters from the edge, subject to the printer’s specifications.

Use the field selector to choose identity data, portrait, signature or static text. Check both sides. Export a template to JSON to move it to another workstation; embedded backgrounds travel with the file. Templates used by approved/issued/revoked records cannot be overwritten. Save them under a revision name instead.

## Enrollment and corrections

Names and card numbers are mandatory. Card numbers must be unique, ignoring letter case. Import a PNG/JPEG portrait or use the connected camera; drag and zoom in the framing dialog. For signatures, use Draw, Import or the Wacom pad action. Uploaded signature images should be dark ink on white or transparent backgrounds. Capture authorization, photo and signature are mandatory for approval in this version.

Save before approval, export or printing. Drafts may be edited. Approved cards require an administrator to Return to draft with a reason. Issued cards cannot be silently edited; revoke the old credential and enroll a replacement with a new unique card number. A reprint is a second physical copy of the same approved identity data, not a data correction.

Closing with unsaved enrollment prompts for discard. Locking preserves unsaved work for the same operator. Ten minutes of idle time triggers a lock. If the application is terminated while locked, unsaved changes are lost; save drafts regularly.

## Printing and failures

Install and configure the printer’s Windows driver before issuance. Select CR80 stock, the correct tray/feed settings and the intended print quality. Choose the exact printer in the print dialog. Test front-only and duplex modes with sample stock; duplex is requested as short-edge flip, whose mapping must be verified with the vendor driver.

The app prints exactly one copy per job. A driver that rejects/substitutes the page size is blocked. The software cannot independently verify the physical stock or edge alignment. It does not perform magnetic stripe or smart-card encoding.

Job states:

| State | Meaning | Operator action |
|---|---|---|
| prepared | Saved before sending to the driver | Wait for submission; if the app closes, recovery changes it to uncertain |
| submitted | Driver submission completed | Inspect actual output; this does not prove a card printed |
| uncertain | Interrupted submission or restart before completion | Inspect physical output and the Windows queue before deciding |
| confirmed | Operator verified the requested output | Card record becomes issued |
| failed | Operator resolved the job as not issued, or a definite failure was recorded | Correct the cause before a new attempt |

Never retry solely because the app was interrupted. A job may already exist in the Windows spooler. Check the output hopper and queue first, clear or cancel unwanted queued copies, then record the outcome in Print history. Automatic retries are deliberately disabled. Confirming a front-only or back-only job confirms only that requested output; operators remain responsible for completing any manual two-pass process. Prefer an automatic duplex printer for two-sided production.

Reprints of issued cards require an administrator and a reason. Expired, revoked or unapproved records are blocked from printer submission. PDFs exported from drafts or revoked records are visibly watermarked. PDF files are outside application access control once exported; treat them as sensitive documents.

## Backup and restore

An administrator chooses Create backup and stores the ZIP on a protected drive. The database backup API makes a consistent copy, including all images and templates. A SHA-256 manifest detects accidental changes; it does not authenticate the source of a backup. The ZIP is not encrypted. Choose a protected/managed backup destination and verify retention and access controls with the organization.

Restore backup verifies the archive, database integrity and supported schema, then writes into a new folder. It never overwrites a live database. Close the app and launch the recovered workspace with:

```powershell
& "$env:LOCALAPPDATA\Programs\CredentialStudio\CredentialStudio.exe" --data-dir "D:\RecoveredCredentialStudio"
```

For ongoing use, the technician can put the same argument in a Windows shortcut. Sign in using credentials from the restored backup. The app’s one-instance lock applies separately to each data directory. Do not put either directory on a network share.

## Support information

Record the application version, Windows version, printer model/driver, signature pad model/SDK, action taken, expected outcome and observed message. Application logs rotate in the data directory and record error classes, avoiding identity-field values and passwords. Do not attach the database, signature images or ID exports to public GitHub issues. Keep a second administrator credential in a controlled password manager; there is no password-reset bypass.
