export const environment = {
  production: true,
  // Same-origin on purpose: production serves the API through the frontend
  // host's /api/* rewrite (Render Static Site → Redirects/Rewrites →
  // Rewrite /api/* to https://moneymind-dy31.onrender.com/api/*).
  // The session lives in httpOnly cookies; hitting the backend's own domain
  // directly would make them third-party cookies, which browsers block —
  // that was the "session expired" login failure in prod.
  apiUrl: '',
  logLevel: 'WARN'
};
