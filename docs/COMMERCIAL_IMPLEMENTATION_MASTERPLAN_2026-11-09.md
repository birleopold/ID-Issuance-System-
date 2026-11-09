# ID-Issuance-System- — implementation and commercialization master plan

**Prepared:** 2026-11-09 · **Status:** planning baseline (not a production sign-off) · **Sequence:** P2 · focused workstation product

> Purpose: a self-contained implementation handoff. Verify current code and ongoing roadmap before creating issues; do not overwrite deployed business logic. This is repository-specific guidance, not evidence that tasks have been completed.

## Market and product decision
**Ideal initial customer:** Schools, membership bodies, SMEs and authorized organizational badges (not government identity issuance without authority).

**Alternatives to benchmark and interview against:** CardPresso; Zebra CardStudio; HID Fargo tooling. Study customer onboarding, top workflows, hidden costs, cancellation, offline operation, support and exported data; avoid copying proprietary screens/code.

**Pricing hypothesis (validate):** One-off installation/license plus hardware setup and annual support; interview 10 badge-printing organizations.

**Offer:** sell a narrow, reliable operational outcome rather than every module at once. First customer discovery: at least ten structured interviews with decision makers; document exact pain, existing tools, willingness to switch, willingness to pay, and procurement blockers. Identify direct and indirect competitors; collect a dated price/feature comparison before setting the public rate.

## Product and implementation workstreams
### P0 — protect customers and fix technical blockers
P0 execute docs/ACCEPTANCE.md on a clean signed Windows build with actual CR80 printer, camera and signature pad; test long names, portrait alignment, duplex, cancellations, jam recovery; never treat job submission as physically printed.

### P1 — complete a genuinely sellable workflow
P1 restrict card templates to authorized brands; audit enrollment, approval, reprint/revocation, encrypted backups, idle lock, operator scopes; build a reproducible customer installation/rollback and export guide.

### P2 — onboarding, administration and repeatable sales
P2 create education-sector bundles with EduManage CSV import; integrate by signed, explicit interchange not shared database; support locally offline without license fail-closed blocking existing cardholder retrieval.

## Detailed engineering backlog and definitions of done
1. **Domain and integrity:** map the authoritative entities, states and external providers; define invariants and allowed transitions; reserve durable identifiers for every financial or irreversible action. All irreversible state changes need append-only evidence and compensating correction, not silent editing.
2. **Interface parity:** list every operator/admin/customer path and its backend endpoint, roles, loading/empty/error/retry/confirmation states. Pair screenshots with real data; keyboard/touch accessibility and responsive layout are acceptance criteria.
3. **Payments or financial records:** require provider-authenticated events, internal reference mapping, unique external event keys, duplicate/delayed callbacks, reconciliation reporting and manually approved exception handling where relevant. Never trust browser 'success' alone.
4. **Operations:** support diagnostics without leaking secrets, admin reversal with reason/actor/time, incident severity playbook, named support channel, metrics/alerts, data export and contract termination.
5. **Deployment:** pin release version; stage migration with backup; validate representative fixtures; expose a smoke command; deploy with health probe; rollback code, restore data only after assessed migration risk; monitor 24–48 hours.
6. **Test pyramid:** unit tests for invariants; PostgreSQL integration for locks and tenant isolation; API/permission matrix; browser/desktop end-to-end; fault injection and backup/restore; customer witnessed acceptance. Classify test evidence as simulated vs hardware/live.

## Pilot acceptance contract
Five full test batches per printer model, physical-print signoff and restore on second PC; preserve data on uninstall; privacy review. Write objective acceptance scenarios, defect log, go/no-go signatories and support expectations. A client pilot is supervised and reversible; avoid using real sensitive information until privacy terms and access controls are approved.

## Commercial go-to-market
- Package a product-led demonstration (<15 minutes), onboarding questionnaire, clear scope exclusions and data-import template.
- Prospect a concentrated initial segment using customer interviews, channel partners and direct demonstrations; record every funnel step rather than buying ads blindly.
- Charge for onsite migration/hardware/training where applicable, separate from recurring platform subscriptions. Offer transparent cancellation, export, retention and renewal.
- Establish unit economics: (net recurring revenue less provider costs, support, hosting, referral fees, taxes where applicable) per active customer; scale only with positive contribution margin and manageable support load.

## Constraints and risks
No unverified performance claims; no regulatory approvals implied. Cross-product integrations must use documented APIs/events, not shared mutable tables. Secrets, payment funds, private records and legal identities require explicit boundary review. Keep existing architecture unless a measured failure justifies changes.

## Project-specific research references
- https://www.zebra.com/
- https://asvs.owasp.org/

## Delivery standards (apply to every milestone)
- **Repository is source of truth.** Begin by checking the latest main, open issues, existing docs, migrations, CI, deployed revision and feature flags. Keep this plan additive: never replace an existing more-specific acceptance register or claim an untested feature is done.
- **Vertical slices:** data schema and transaction boundaries → backend/domain service → tenant/role permissions and API → server-rendered or desktop UI → tests → migrations and fixtures → monitoring and support docs → rollout/rollback. No backend-only 'complete' status.
- **Security & privacy:** threat model and data-flow inventory, least privilege, 2FA for privileged operations, audit logs, credentials only in secret stores, dependency scanning and OWASP ASVS 5.0 verification where applicable; use NIST SSDF as release process. Apply Uganda PDPO obligations after legal review.
- **Reliability:** migration dry-run; concurrency/idempotency fault injection; backup and tested restore; CI green at pinned commit; UX on constrained bandwidth/small screens; smoke checks before and after deployment. Record environment, tests and observed failures, not just pass claims.
- **Commercial readiness:** one landing page and honest demo, clear limitations, written price experiment, terms/data processing/support, onboarding, renewals, refunds, deletion/export, buyer interview log and customer support ownership. Charges must reflect actual infrastructure, fees, sales, support, taxes and churn.
- **Evidence register:** for each task record owner, issue/PR, change SHA, affected screens/APIs/tables, test command/results, screenshot where relevant, dependencies, deployment and rollback SHA, customer acceptance, and remaining gaps. **No project is production-certified by this document.**

## Milestone governance and stop rules
- **M0 discovery (week 1):** inspect existing backlog against this plan and tag Verified / Partially implemented / Planned / Blocked; customer interviews and competitor/pricing evidence with dates.
- **M1 correctness and security (weeks 2–4):** address P0s and add executable regression cases; exit only with CI, migration and restore evidence.
- **M2 complete narrow workflow (weeks 4–8):** one supported target segment and one end-to-end paid use case; exit only with UI and runbook acceptance.
- **M3 controlled pilot (weeks 8–12):** named organizations, support response plan, signed limitations and paid conversion decision; exit if no critical failure and economics are acceptable.
- **M4 scale (after proof):** referrals, partners, self-service signup, measured renewal, performance and privacy; decline speculative features without customer evidence.

## KPI and decision protocol
Track weekly: qualified leads, demos, successful onboarding, activation, trial-to-paid, monthly/term revenue, gross margin, payment leakage, tickets per customer, severity-1 incidents, restores tested and churn. At each milestone choose **ship / repair / pause** using evidence. Avoid custom forks; use configurable product packages with stable upgrade paths.

## Baseline research and ongoing verification
- NIST SSDF: https://csrc.nist.gov/projects/ssdf
- OWASP ASVS 5.0: https://asvs.owasp.org/
- Uganda PDPO registration guidance: https://doingbusiness.finance.go.ug/licensing/pdpo-data-protection-registration
- These references inform controls, not automatic legal clearance. Verify current local requirements before contracting.
