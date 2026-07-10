# Project Structure

MoneyMind is a monorepo with two independent apps: `backend/` (Flask) and `frontend/` (Angular). They communicate over HTTP — no shared code between them.

```
MoneyMind/
├── backend/
│   ├── app.py                  # Flask app factory, blueprint registration, db.create_all()
│   ├── requirements.txt
│   ├── .env                    # Local secrets (never commit)
│   ├── models/                 # SQLAlchemy models (one class per file)
│   │   ├── user.py             # User + db = SQLAlchemy() instance
│   │   ├── transaction.py
│   │   ├── budget.py
│   │   ├── goal.py
│   │   └── plaid_item.py
│   ├── routes/                 # Flask Blueprints (one per domain)
│   │   ├── auth.py             # /api/auth
│   │   ├── transactions.py     # /api/transactions
│   │   ├── budgets.py          # /api/budgets
│   │   ├── goals.py            # /api/goals
│   │   ├── analytics.py        # /api/analytics
│   │   ├── plaid.py            # /api/plaid
│   │   └── chat.py             # /api/chat
│   └── utils/
│       ├── plaid_client.py     # Plaid SDK initialization
│       ├── openai_client.py    # OpenAI client setup
│       ├── financial_context.py # Builds user context for AI chat
│       ├── categories.py       # Shared transaction category constants
│       └── logger.py           # Backend logging utility
│
└── frontend/
    ├── angular.json
    ├── package.json
    └── src/
        ├── environments/       # environment.ts / environment.prod.ts (apiUrl)
        ├── styles.scss         # Global styles
        └── app/
            ├── app.ts          # Root component
            ├── app.routes.ts   # Route definitions
            ├── app.config.ts   # App-level providers
            ├── components/     # Feature UI components (one folder per component)
            │   ├── login/
            │   ├── register/
            │   ├── dashboard/
            │   ├── budget-manager/
            │   ├── goals-manager/
            │   ├── chat/
            │   ├── transaction-form/
            │   ├── navigation/
            │   └── modals/
            ├── services/       # Injectable services (API communication)
            │   ├── auth.service.ts
            │   ├── transactionService.ts
            │   ├── budget.service.ts
            │   ├── goal.service.ts
            │   ├── chat.service.ts
            │   ├── category.service.ts
            │   ├── modal.service.ts
            │   └── logger.service.ts
            ├── guards/
            │   └── auth.guard.ts   # Redirects unauthenticated users to /login
            └── types/
                ├── chat.d.ts
                └── plaid.d.ts
```

## Key Conventions

### Backend

- Each domain has one Blueprint in `routes/` registered in `app.py` with a `/api/<domain>` prefix
- All protected routes use `@jwt_required()` decorator
- Models import `db` from `models/user.py` (the single SQLAlchemy instance)
- Models expose a `to_dict()` method for JSON serialization
- Snake_case for all Python identifiers

### Frontend

- All components are **standalone** (Angular 20 style — no NgModules)
- Each component lives in its own folder with `.ts`, `.html`, `.scss`, and `.spec.ts` files
- Services are `providedIn: 'root'` singletons
- API base URL comes from `environment.apiUrl` — never hardcode URLs in components or services
- JWT token stored in `localStorage` as `access_token`; all authenticated requests send `Authorization: Bearer <token>`
- Use `LoggerService` for all logging (not `console.log` directly)
- camelCase for TypeScript identifiers; SCSS scoped per component

### Adding a New Feature

1. **Backend**: add model in `models/`, add blueprint in `routes/`, register in `app.py`
2. **Frontend**: add component folder in `components/`, add service method in `services/`, add route in `app.routes.ts`
3. Protect backend endpoints with `@jwt_required()`
4. Use `authGuard` on new frontend routes that require login
