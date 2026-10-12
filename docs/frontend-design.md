# Frontend design implementation

Implemented the root `DESIGN.md` in the existing Stage 1 frontend on 12 October 2026.

## Visual treatment

Sky background, white paper workspace, graphite text, orange actions, and ember footer follow the supplied palette. Jersey 10 is limited to display headings; Manrope is used for controls and prose. Both fonts are served locally with their OFL licenses. Clouds, robot, and gavel are original flat SVG pixel grids with crisp edges. Asset sources are documented in `web/assets/README.md`.

The workbench uses traffic-light window chrome, a desktop sidebar, and horizontal navigation on phones. Shadows, rounded cards, focus rings, hover states, and gentle cloud motion follow the design. Reduced-motion preferences disable drifting clouds and smooth navigation.

## Working interactions

- Repair desk, Run evidence, and Training log remain mounted so tab changes preserve drafts and polling.
- Source code, Contract, and Test cases use nested accessible tabs with arrow keys and Home/End navigation.
- Presets fill the actual request and reset property consent. Validation opens the affected editor panel.
- The source editor supports indentation, line numbers, and Ctrl/Cmd+Enter submission.
- Accepted runs open Run evidence. Both cancel controls use the existing cancellation operation.
- Candidate diffs and expandable sources, execution drilldowns, report/patch downloads, training charts, and measured evaluation tables use the existing live data.
- Execution and evaluation tables provide contained keyboard-accessible scrolling; matrix scrolling survives redraws.

The frozen API contract and backend are unchanged. The screen retains explicit fixture labeling, bounded verification scope, and factual Stage 1/Stage 2 role descriptions. Evaluation values and curves are never fabricated.

## Verification

- 34 frontend tests passed, including malformed domain/test-entry regression cases.
- 106 backend tests passed; 9 hardware/sandbox tests were deselected in this general suite.
- 11 mock API tests and the frontend asset/API smoke harness passed. The smoke harness is explicitly fixture-based.
- Canonical schema checksum and all canonical/frontend fixtures passed validation.
- Browser review confirmed nested keyboard tabs, consent/error routing, preset consistency, retained drafts, live cancellation, automatic evidence navigation, and downloads.
- A real local sum repair produced a supported patch with 67 admitted checks and 135 executions. The downloaded source hash matched the selected candidate. This public mechanics example is unscored and overlaps the training family.
- All three workspace panels were checked at actual viewport widths 320, 375, 768, 1024, and 1440 pixels. No page overflow or uncontained elements were found. Populated live evidence was also checked across these widths.
- Desktop and mobile screenshots were visually inspected for alignment, text wrapping, controls, and decorative placement. Browser font loading succeeded and no browser errors or warnings were recorded during review.

Local screenshots, measured viewport records, and the real repair report are retained in ignored `backend/artifacts/design-review/`. They are review evidence, not shipped fixtures. The user's original browser draft was preserved by using separate review tabs.
