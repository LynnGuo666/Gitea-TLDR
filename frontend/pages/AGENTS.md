# PAGE PATTERNS

## OVERVIEW
- Route files in this directory define page-level orchestration; shared concerns live in `components/` and `lib/`.

## PAGE CHECKLIST
- Start with `Head` title and semantic header components.
- Drive data via backend API endpoints only.
- Implement full UI state set: loading, error, empty, success.
- Keep page-specific fetch functions local; extract reusable pieces when used across pages.

## ROUTE-SPECIFIC PATTERNS
- `index.tsx`: dashboard/repo list and filters.
- `usage.tsx`, `reviews.tsx`, `settings.tsx`, `preferences.tsx`: feature dashboards with refresh and state messaging.
- `admin/*`: admin surfaces; permission assumptions must be explicit and aligned with backend.
- `repo/[owner]/[repo].tsx`: dynamic route; guard on `router.isReady` before using params.

## COMMON IMPLEMENTATION RULES
- Use `PageHeader` for page title (`h1`), `SectionHeader` for sections (`h2`).
- Keep fetch calls wrapped in `try/catch` with user-visible fallback text.
- Avoid ad-hoc API URL building; use endpoint strings with `apiFetch`.
- Prefer declarative rendering over imperative DOM logic.

## ANTI-PATTERNS
- Do not redirect away silently on permission failures without user feedback.
- Do not duplicate auth polling logic inside individual pages.
- Do not hardcode model/provider assumptions in UI labels.
