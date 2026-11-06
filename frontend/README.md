# React preview

This frontend is an isolated Phase 7 migration surface. It does not replace the Flask-rendered page at / and does not mount React into the legacy page.

## Local development

Run the Flask application in one terminal:

    python app.py

Install the frontend dependencies and start Vite in another terminal:

    npm --prefix frontend install
    npm --prefix frontend run dev

Open http://127.0.0.1:5173. Vite proxies /api, /static, and /admin requests to the Flask server at http://127.0.0.1:5000. Set FLASK_API_PROXY_TARGET to override that backend address.

## Flask preview route

Build the frontend bundle:

    npm --prefix frontend run build

The build is written to static/react-preview. Flask serves it at /preview/ and its assets below that path. The build directory is generated output and is intentionally not committed.

When no build is present, /preview/ returns a clear 503 page rather than silently changing or replacing the existing main page.

## Migration boundaries

- The existing / route continues to render templates/index.html and use static/app.js.
- React owns only its own #root element on the isolated preview page.
- Flask remains responsible for API requests, Nexon integrations, growth calculations, persistence, AI providers, and admin authentication.
- The React API client uses same-origin credentials and relative /api paths. Local Vite uses a development proxy, so CORS is not required.
- Existing sessionStorage and localStorage keys are not cleared, renamed, or rewritten by this preview foundation. Their schemas must be explicitly mapped and tested before future React features start reading or writing them.
- The legacy page, including its detailed character preset and tooltip interactions, remains available until feature parity and regression tests are complete.