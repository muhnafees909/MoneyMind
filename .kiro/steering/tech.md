# Tech Stack

## Backend

- **Runtime**: Python 3
- **Framework**: Flask 3.1 with Blueprints for route organization
- **ORM**: SQLAlchemy 2.0 via Flask-SQLAlchemy
- **Database**: PostgreSQL (psycopg2-binary driver)
- **Auth**: JWT via Flask-JWT-Extended (3-hour token expiry), passwords hashed with Werkzeug
- **External APIs**: Plaid (plaid-python 37.0), OpenAI (>=1.3.0)
- **WSGI**: Gunicorn for production
- **Config**: python-dotenv for environment variables

## Frontend

- **Framework**: Angular 20 (standalone components)
- **Language**: TypeScript 5.9, strict mode enabled (`noImplicitAny` disabled for flexibility)
- **UI Library**: Angular Material 20 + CDK
- **Styling**: SCSS (per-component + global `styles.scss`)
- **HTTP**: Angular `HttpClient` with RxJS Observables
- **Markdown rendering**: ngx-markdown + marked
- **Testing**: Karma + Jasmine, coverage via karma-coverage
- **Formatter**: Prettier (printWidth: 100, singleQuote: true)
- **Build tool**: Angular CLI 20 / `@angular/build:application`

## Environment Variables (Backend `.env`)

```
JWT_SECRET_KEY=
DATABASE_URL=postgresql://...
PLAID_CLIENT_ID=
PLAID_SECRET=
PLAID_ENV=sandbox
OPENAI_API_KEY=
```

---

## Common Commands

### Frontend (`cd frontend`)

```bash
npm install              # Install dependencies
npm start                # Dev server → localhost:4200
npm run build            # Production build
npm run build:prod       # Explicit production build
npm test                 # Run unit tests (Karma, watch mode)
npm run watch            # Dev build in watch mode
```

### Backend (`cd backend`)

```bash
python -m venv venv          # Create virtual environment (first time)
venv\Scripts\activate        # Activate venv (Windows)
pip install -r requirements.txt
python app.py                # Dev server → localhost:5000
```

### Database

Tables are auto-created on first run via `db.create_all()` in `app.py`. No migration tool is currently in use — schema changes require manual handling in production.
