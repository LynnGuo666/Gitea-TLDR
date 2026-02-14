# FRONTEND GUIDE

## OVERVIEW
- `frontend/` is Next.js pages-router UI; shared shell in `Layout`, route pages in `pages`, reusable logic in `lib`.

## STRUCTURE
```text
frontend/
├── pages/              # route files (_app, index, admin/*, repo/[owner]/[repo])
├── components/         # reusable UI and app shell
├── lib/                # API/auth/hooks/types/version helpers
└── styles/             # global styles
```

## ARCHITECTURE RULES
- Use `apiFetch` from `frontend/lib/api.ts` for all backend requests.
- Keep auth/session state flow centralized through `AuthContext` and `lib/auth.ts` helpers.
- Use `PageHeader` (`h1`) and `SectionHeader` (`h2`) for title semantics.
- Keep pages mostly composition/orchestration; move reusable logic to `lib/` or `components/`.

## TYPING + STATE
- No `any`; use explicit types from `frontend/lib/types.ts`.
- For async UI, handle all states: loading, error, empty.
- Prefer small local hooks/utilities (`useDebounce`, `useWindowFocus`) over duplicated effect logic.

## ROUTING CONVENTIONS
- Pages Router only (`pages/*.tsx` + nested folders).
- Dynamic route pattern: `pages/repo/[owner]/[repo].tsx`.
- Admin pages live under `pages/admin/*`.
- App-wide providers and shell remain in `_app.tsx` + `components/Layout.tsx`.

## ANTI-PATTERNS
- Do not call Gitea/Claude endpoints directly from browser.
- Do not scatter one-off title typography classes when shared headers exist.
- Do not gate admin UI by logged-in status only; use explicit admin status.
- Do not edit generated outputs (`frontend/.next`, `frontend/out`, `node_modules`).

## VERIFY FOR FRONTEND CHANGES
```bash
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```
