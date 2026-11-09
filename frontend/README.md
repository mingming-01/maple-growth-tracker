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

The build is written to `static/react-preview/`. Flask serves that build at the single public application path, `/`, using the absolute `/static/react-preview/` asset base.

- `/`: serves the React dashboard.
- If the React build is missing, Flask returns HTTP 503. It never falls back to an obsolete UI.
- The former `/legacy/` and `/preview/` routes have been retired.

For Render, use this Build Command:

    pip install -r requirements.txt && npm --prefix frontend install --no-audit --no-fund && npm --prefix frontend run build

## Migration boundaries

- React owns its own root element and does not mount into the legacy page.
- Flask APIs and server-side integrations remain the source of truth.
- Existing sessionStorage/localStorage keys and schemas are preserved for page state, favorites, growth goals, and AI response cache.
- Keep Flask responsible for APIs, integrations, persistence, and administrator authentication; the React build is the only public application UI.
