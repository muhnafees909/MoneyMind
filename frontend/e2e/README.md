# MoneyMind E2E Regression Suite (Playwright)

End-to-end tests for the core user flows, driven through the real browser
against a running frontend + backend.

## Covered flows

| Spec | Flow |
|------|------|
| `login.spec.ts` | Sign in (valid + wrong-password) |
| `transaction-add.spec.ts` | Add a manual transaction |
| `transaction-category.spec.ts` | Edit a transaction's category inline |
| `envelope.spec.ts` | Create a goal and allocate money into it |
| `budget.spec.ts` | Create a monthly budget |

## Design notes

- **Accessibility-tree selectors only** (`getByRole` / `getByLabel` /
  `getByPlaceholder`) — no brittle CSS/class selectors for interactions.
- **Isolated data**: every test provisions a fresh, unique user via the backend
  API (`e2e/fixtures.ts`) and then signs in through the UI. Tests are
  independent and run in parallel.

## Prerequisites

1. **Postgres** running with the schema migrated (`flask db upgrade`).
2. **Backend** on `http://localhost:5000`:
   ```
   cd backend && venv\Scripts\activate && python app.py
   ```
3. **Install Playwright** (first time only):
   ```
   cd frontend
   npm install
   npx playwright install
   ```

The Angular dev server (`http://localhost:4200`) is started automatically by the
Playwright config if it isn't already running.

## Run

```
cd frontend
npm run e2e            # headless
npm run e2e:ui         # interactive UI mode
npm run e2e:report     # open the last HTML report
```

Override URLs if needed: `E2E_BASE_URL`, `E2E_BACKEND_URL`.
