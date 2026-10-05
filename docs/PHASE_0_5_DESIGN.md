# Phase 0.5 frontend design brief

## Direction

The interface follows a documentation-first pattern: fixed top bar, grouped left navigation, a narrow reading column, and a contextual right rail. It uses the structure and density of mature API documentation while remaining an operational decision-support interface.

## Tokens

### Color

- Canvas: `#FFFFFF`
- Heading: `#000000`
- Body: `#111111`
- Muted: `#6B6B6B`
- Divider: `#E5E5E5`
- Code/table surface: `#F7F7F7`
- Data-only accent: `#8A5A36`

### Typography

- Text: `Inter`, then system UI fallbacks
- Code, IDs, and numbers: `JetBrains Mono`, then system monospace fallbacks
- Scale: `12 / 14 / 16 / 20 / 28 / 40px`
- Weights: `400 / 500 / 600`
- Body line height: `1.6`

### Spacing

Only the 8px scale is used: `8 / 16 / 24 / 32 / 48 / 64px`.

## Component rules

- Hierarchy uses typography, whitespace, and 1px rules.
- Primary actions are black; secondary actions are white with a black border.
- Status tags are unfilled, monospace, and outlined.
- Code blocks use a light surface, one border, a language label, and a copy action.
- Callouts use a white background, one border, and a 3px black left rule.
- Tables use sticky light-grey headers, thin row rules, and right-aligned monospace numerals.
- Page navigation always exposes previous and next destinations.
- The right contents rail collapses first. The left navigation becomes a menu below 900px.
- Focus indicators remain visible for keyboard users.

## Phase boundary

All numerical results and operational states are deterministic Phase 0.5 fixtures. The frontend does not perform geological alignment, trajectory calculation, OCR, transferability scoring, or risk calibration.

## Self-review

- No gradients, shadows, glass effects, blur, glows, or decorative animation.
- No marketing hero, centered sales copy, feature-card grid, or hype language.
- No UI chrome accent color. The single muted brown is restricted to risk/data marks.
- No corner radius above 4px except circular map/timeline data marks.
- No decorative imagery or icon-in-circle feature treatment.
- Empty, loading, provider-error, and no-result states are defined.
- The interface uses semantic landmarks, labels, tables, headings, and focus rings.

