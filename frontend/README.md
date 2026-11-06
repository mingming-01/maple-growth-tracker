# React frontend

The React/Vite dashboard is the primary frontend when the production build exists. Flask continues to own the backend APIs, Nexon integrations, AI services, persistence, and admin authentication.

## Local development

Run Flask in one terminal:

    python app.py

Install frontend dependencies and start Vite in another terminal:

    npm --prefix frontend install
    npm --prefix frontend run dev

Open http://127.0.0.1:5173. Vite proxies `/api`, `/static`, and `/admin` requests to Flask at http://127.0.0.1:5000. Set `FLASK_API_PROXY_TARGET` to override the backend address.

## Production build and routes

Build the frontend:

    npm --prefix frontend run build

The build is written to `static/react-preview/`. In production builds, assets use the absolute `/static/react-preview/` base path, so the same output works when Flask serves the app at both `/` and `/preview/`.

- `/`: serves React when `static/react-preview/index.html` exists; otherwise safely falls back to the legacy Flask page.
- `/preview/`: serves the React dashboard for verification and comparison.
- `/legacy/`: preserves the previous Vanilla JS interface.

For Render, use this Build Command:

    pip install -r requirements.txt && npm --prefix frontend install --no-audit --no-fund && npm --prefix frontend run build

## Migration boundaries

- React owns its own root element and does not mount into the legacy page.
- Flask APIs and server-side integrations remain the source of truth.
- Existing sessionStorage/localStorage keys and schemas are preserved for page state, favorites, growth goals, and AI response cache.
- Keep `/legacy/` available until the production URL has been verified and the migration is accepted.
