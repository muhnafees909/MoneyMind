# MoneyMind

MoneyMind is a comprehensive personal finance management application that helps users track their spending, manage budgets, set financial goals, and gain insights into their financial health. The application integrates with Plaid to automatically sync bank transactions and provides intelligent analytics to help users make better financial decisions.

## Features

### Transaction Management
- Manual transaction entry with customizable categories
- Automatic transaction syncing via Plaid integration
- Categorization of expenses and income
- Detailed transaction history with filtering and search
- Pagination support for large transaction lists

### Budget Tracking
- Create and manage monthly budgets by category
- Real-time budget vs actual spending comparison
- Visual progress indicators for each budget category
- Budget alerts when approaching or exceeding limits

### Financial Goals
- Set and track financial goals with target amounts and deadlines
- Add incremental progress toward goals
- Visual progress tracking with percentage completion
- Automatic status updates based on target dates

### Analytics Dashboard
- Spending breakdown by category with interactive pie charts
- Monthly spending trends and comparisons
- Financial insights and spending patterns
- Visual representations of budget adherence

### AI Financial Advisor
- Chat-based financial assistant powered by OpenAI
- Personalized insights based on your spending habits
- Budget recommendations and financial tips
- Context-aware responses using your transaction history

### Bank Integration
- Secure connection to bank accounts via Plaid
- Automatic transaction synchronization
- Support for multiple financial institutions
- Webhook-based updates for real-time transaction syncing

## Technology Stack

### Backend
- **Framework**: Flask (Python)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT tokens with flask-jwt-extended
- **External APIs**: Plaid API for bank connectivity, OpenAI API for financial advisor
- **Deployment**: Render

### Frontend
- **Framework**: Angular 20
- **UI Library**: Angular Material
- **State Management**: RxJS Observables
- **Styling**: SCSS
- **Deployment**: Render (static site)

## Getting Started

### Prerequisites
- Python 3.8 or higher
- Node.js 18 or higher
- PostgreSQL database
- Plaid API credentials (client ID and secret)
- OpenAI API key

### Backend Setup

1. Clone the repository and navigate to the backend directory:
```bash
cd backend
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with the following variables:
```
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://username:password@localhost/moneymind_dev
PLAID_CLIENT_ID=your_plaid_client_id
PLAID_SECRET=your_plaid_secret
PLAID_ENV=sandbox
OPENAI_API_KEY=your_openai_api_key
```

5. Initialize the database:
```bash
python migrate_db.py
```

6. Start the development server:
```bash
python app.py
```

The backend server will start on `http://localhost:5000`.

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Update the environment configuration in `src/environments/environment.ts`:
```typescript
export const environment = {
  production: false,
  apiUrl: 'http://localhost:5000'
};
```

4. Start the development server:
```bash
npm start
```

The frontend application will start on `http://localhost:4200`.

## Project Structure

### Backend
```
backend/
├── models/           # Database models (User, Transaction, Budget, FinancialGoal, PlaidItem)
├── routes/           # API endpoints organized by feature
├── utils/            # Utility functions and helpers
├── app.py            # Application entry point
└── migrate_db.py     # Database initialization script
```

### Frontend
```
frontend/
├── src/
│   └── app/
│       ├── components/     # UI components
│       ├── services/       # API communication services
│       ├── types/          # TypeScript interfaces
│       └── guards/         # Route guards for authentication
```

## API Documentation

### Authentication Endpoints
- `POST /api/auth/register` - Create a new user account
- `POST /api/auth/login` - Authenticate and receive JWT token
- `GET /api/auth/me` - Get current user information

### Transaction Endpoints
- `GET /api/transactions` - Retrieve all transactions
- `POST /api/transactions` - Create a new transaction
- `PUT /api/transactions/:id` - Update a transaction
- `DELETE /api/transactions/:id` - Delete a transaction

### Budget Endpoints
- `GET /api/budgets` - Retrieve all budgets
- `POST /api/budgets` - Create a new budget
- `PUT /api/budgets/:id` - Update a budget
- `DELETE /api/budgets/:id` - Delete a budget
- `GET /api/budgets/progress` - Get budget progress for a specific month

### Goal Endpoints
- `GET /api/goals` - Retrieve all financial goals
- `POST /api/goals` - Create a new goal
- `PUT /api/goals/:id` - Update a goal
- `DELETE /api/goals/:id` - Delete a goal
- `POST /api/goals/:id/add-progress` - Add progress to a goal

### Analytics Endpoints
- `GET /api/analytics/spending-by-category` - Get spending breakdown by category
- `GET /api/analytics/monthly-spending` - Get monthly spending trends
- `GET /api/analytics/spending-summary` - Get overall spending summary

### Plaid Endpoints
- `POST /api/plaid/create-link-token` - Generate Plaid Link token
- `POST /api/plaid/exchange-public-token` - Exchange public token for access token
- `POST /api/plaid/sync-transactions` - Manually sync transactions
- `POST /api/plaid/webhook` - Webhook endpoint for automatic updates

### AI Advisor Endpoints
- `POST /api/chat` - Send a message to the AI financial advisor

## Security Features

- JWT-based authentication with 3-hour token expiration
- Password hashing using Werkzeug security utilities
- CORS protection configured for specific origins
- Plaid webhook signature verification support
- Secure credential storage in environment variables

## Development Notes

### Database Migrations
The application uses SQLAlchemy ORM with automatic table creation via `db.create_all()`. For production environments, consider implementing proper database migrations using Flask-Migrate.

### Plaid Integration
The application uses Plaid's Transactions Sync API for efficient transaction retrieval. Webhooks are configured to automatically sync new transactions when they become available from financial institutions.

### Transaction Deduplication
Plaid transactions are automatically deduplicated using the `plaid_transaction_id` field. The system prevents duplicate entries even if the same transaction is synced multiple times.

### AI Financial Advisor
The chatbot uses OpenAI's GPT model with custom system prompts to provide financial advice based on user transaction data. Conversations are contextual and maintain chat history for coherent interactions.

## Deployment

### Backend Deployment (Render)
1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Set environment variables in Render dashboard
4. Deploy from the main branch

### Frontend Deployment (Render)
1. Build the production application: `npm run build`
2. Deploy the `dist` folder as a static site
3. Configure environment variables for production API URL

### Webhook Configuration
After deploying to production, configure the webhook URL in your Plaid dashboard:
```
https://your-production-url.com/api/plaid/webhook
```

## Contributing

Contributions are welcome. Please follow these guidelines:
- Write clear commit messages
- Add tests for new features
- Update documentation as needed
- Follow existing code style and conventions

## License

This project is private and proprietary.

## Support

For questions or issues, please open an issue in the GitHub repository.
