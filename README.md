# Krishi-AI

Krishi-AI is a prototype farming-assistance project with a Streamlit interface, a FastAPI service, and a bundled commodity-price CSV. It is not currently a production-ready agricultural recommendation or disease-diagnosis system.

Repository: <https://github.com/AarDew/Krishi-AI>

## Current functionality and limitations

- The Streamlit UI provides farmer and buyer views, a state map, commodity-price analysis, and forms that call the backend.
- The frontend reads the bundled commodity-price data in `backend/commodity_price.csv`.
- FastAPI exposes health, login/signup, farm-submission, crop, disease, marketplace, and chat endpoints.
- Signup/login, farm submission, commodity data, and marketplace listings use the SQLite-backed API. The login token is still a demo token, and the marketplace seeds sample listings when empty. Crop recommendations use the trained Random Forest in `backend/models/crop_recommendation_model.joblib`; disease detection remains unavailable because its model is not included.
- The bundled crop classifier is not a substitute for agronomic advice. Disease detection is not implemented, and no `crop_data.csv` or trained disease model is included.
- Detailed weather and market trend views include simulated data; they are not verified forecasts or live market quotes.
- Schedule generation and chat are exposed through FastAPI and require `GEMINI_API_KEY`; they call the external Gemini service. Their behavior has not been verified without a real API credential.
- The project owner reports these existing deployment URLs; this local code change does not deploy or verify them:

- Backend: <https://krishi-ai-backend-dd02.onrender.com>
- Frontend: <https://krishi-ai-u95h8cakf5eipayejtsbx6.streamlit.app/>

## Architecture

```text
Browser
  |
  v
Streamlit UI (frontend/streamlit_run.py)
  | HTTP requests (BACKEND_URL)
  v
FastAPI (backend/main.py)
  |
  +-- SQLite schema and commodity CSV initialization (backend/krishiai.db)
  +-- Trained crop classifier (backend/models/crop_recommendation_model.joblib)
```

## Project layout

```text
backend/
  commodity_price.csv
  main.py
  database.py
  crop_advisor.py
  models/
frontend/
  commodity_price.csv
  streamlit_run.py
backend/requirements.txt
frontend/requirements.txt
requirements.txt
```

`backend/main.py` uses SQLAlchemy and `backend/krishiai.db`. `backend/database.py` is a separate SQLite helper for `users.db` and `crop_prices.db`; the FastAPI application does not currently import it.

## Technologies

- Python 3.11
- FastAPI and Uvicorn
- Streamlit
- SQLAlchemy and SQLite
- Pandas, NumPy, Plotly, Folium, and Geopy
- Google Gen AI client for optional Gemini-backed schedule generation and chat

## Local setup (Windows PowerShell)

From the cloned repository directory:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The root requirements file installs both sets of dependencies. To install only one application:

```powershell
python -m pip install -r backend\requirements.txt
python -m pip install -r frontend\requirements.txt
```

Start the backend in one PowerShell window:

```powershell
$env:CORS_ORIGINS = "http://localhost:8501,http://127.0.0.1:8501"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Start Streamlit in a second window:

```powershell
$env:BACKEND_URL = "http://127.0.0.1:8000"
python -m streamlit run frontend\streamlit_run.py
```

The backend defaults to `backend/krishiai.db`; it creates missing tables without deleting the database. Set `KRISHIAI_DB_PATH` to an absolute path to select another SQLite file. Set `CORS_ORIGINS` to a comma-separated list of allowed browser origins. Set `BACKEND_URL` in the frontend environment to the backend base URL.

Optional API configuration is read from environment variables: `OPENWEATHER_API_KEY`, `GEMINI_API_KEY`, `AGRICULTURE_PRICE_API_URL`, and `AGRICULTURE_PRICE_API_KEY`. Gemini schedule/chat endpoints return HTTP 503 when `GEMINI_API_KEY` is absent. The OpenWeather and agricultural-price helpers are not connected to the active routes. The price helper sends its optional key as a Bearer token. Never commit credentials or a populated `.env` file.

## API

With the backend running:

- Interactive API documentation: <http://127.0.0.1:8000/docs>
- Health check: `GET /health`
- Endpoints: `POST /login/`, `POST /signup/`, `POST /submit_farm_data/`, `POST /recommend-crop`, `POST /predict_crop/` (legacy, unavailable), `POST /detailed_analysis/`, `POST /detect_disease/`, `POST /get_crop_schedule/`, `GET /get_farmers/`, `GET /commodity_prices/`, `GET /marketplace/listings/`, `POST /marketplace/list/`, and `POST /chat/`

Signup/login and farm submission use SQLite, but login still returns a demo token. The marketplace stores listings in SQLite and inserts sample listings if the table is empty. The `/recommend-crop` endpoint uses the bundled classifier; the legacy `/predict_crop/` and disease endpoint remain unavailable. Gemini endpoints need a valid key and have not been tested against the external service.

## Deployment

### Render (FastAPI)

- Repository: `AarDew/Krishi-AI`
- Branch: `main`
- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Set `PYTHON_VERSION=3.11.0`.
- Keep `models/crop_recommendation_model.joblib` in the backend deployment. At 10.52 MiB, it is suitable to commit with the app and below GitHub's 100 MiB per-file limit. The model loader resolves it relative to `backend/main.py`; `scikit-learn` is pinned to the artifact's training version (1.6.1).
- Set `CORS_ORIGINS` to the exact Streamlit Community Cloud origin.
- Mount a persistent disk at `/var/data` and set `KRISHIAI_DB_PATH=/var/data/krishiai.db`.
- Set `GEMINI_API_KEY` only if schedule generation and chat are needed.

### Streamlit Community Cloud

- Repository: `AarDew/Krishi-AI`
- Branch: `main`
- Main file path: `frontend/streamlit_run.py`
- Add this to the app's secrets after Render is deployed:

  ```toml
  BACKEND_URL = "https://<your-render-service>.onrender.com"
  ```

  Alternatively, set `BACKEND_URL` as an environment variable. Configure the Render `CORS_ORIGINS` value to the actual Streamlit app origin. Do not use placeholder URLs as deployment URLs.

Before public submission, verify the deployed `/health` endpoint and exercise the frontend against the actual Render URL. Configure persistent SQLite storage for Render; the default service filesystem may be ephemeral. Crop and disease model assets remain absent, and the login token is not production authentication.

## Screenshots

No screenshots are currently included.
