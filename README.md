# Spotcraft — ACD Plan Builder

Media planners upload an Average Commercial Duration (ACD) plan, define edit dispersion (e.g., 30s/20s/10s at 60/30/10%), configure campaign & per-channel daily rates, and download a full Edit-wise + Day-wise schedule Excel.

## Stack
- **Frontend**: React 19 + Tailwind + Shadcn/UI
- **Backend**: FastAPI + Motor (MongoDB async)
- **Database**: MongoDB
- **Excel**: openpyxl

## Local development

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.deploy.txt
cp .env.example .env  # fill MONGO_URL, DB_NAME, CORS_ORIGINS
uvicorn server:app --reload --port 8001
```

### Frontend
```bash
cd frontend
yarn install
echo "REACT_APP_BACKEND_URL=http://localhost:8001" > .env
yarn start
```

Open http://localhost:3000.

## Free deployment: Vercel + Render + MongoDB Atlas

### 1. MongoDB Atlas (free 512 MB cluster)
1. Sign up at https://cloud.mongodb.com → create a **M0 Free** cluster
2. **Database Access** → add a DB user (username + password)
3. **Network Access** → add `0.0.0.0/0` (allow from anywhere)
4. **Connect** → **Drivers** → copy the SRV connection string, e.g.
   `mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`

### 2. Render (free backend)
1. Sign in to https://render.com with GitHub
2. **New +** → **Web Service** → connect this repo
3. **Root directory**: `backend`
4. **Build command**: `pip install -r requirements.deploy.txt`
5. **Start command**: `uvicorn server:app --host 0.0.0.0 --port $PORT`
6. **Environment variables**:
   - `MONGO_URL` = your Atlas SRV string
   - `DB_NAME` = `spotcraft`
   - `CORS_ORIGINS` = `*` (tighten to your Vercel domain later)
   - `PYTHON_VERSION` = `3.11.9`
7. Click **Create Web Service** → wait ~5 min → note your Render URL (e.g., `https://spotcraft-backend.onrender.com`)

> **Note**: Render's free tier sleeps after 15 min of inactivity — first request wakes it in ~30 s.

### 3. Vercel (free frontend)
1. Sign in to https://vercel.com with GitHub
2. **Add New** → **Project** → import this repo
3. **Root directory**: `frontend`
4. **Framework preset**: Create React App (auto-detected)
5. **Environment variables**:
   - `REACT_APP_BACKEND_URL` = your Render URL from step 2
6. **Deploy** → you'll get a permanent URL like `https://spotcraft.vercel.app`

### 4. Tighten CORS
Go back to Render, set `CORS_ORIGINS` to your exact Vercel URL, and redeploy.

Share `https://spotcraft.vercel.app` with your team.

## License
Personal / internal use.
