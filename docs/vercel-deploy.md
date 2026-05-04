# Deploy the AI Saathi Frontend to Vercel

The backend is already hosted on Render at:

```text
https://ai-saathi-1.onrender.com
```

Use Vercel only for the Next.js frontend in `frontend/`. Keep the Python backend on Render to avoid build and runtime conflicts.

## 1. Import the project

1. Push this repository to GitHub.
2. In Vercel, choose **Add New Project**.
3. Import the GitHub repository.
4. Set **Root Directory** to:

```text
frontend
```

Vercel should detect **Next.js** automatically.

## 2. Build settings

Use these settings if Vercel does not fill them automatically:

```text
Framework Preset: Next.js
Install Command: npm install
Build Command: npm run build
Output Directory: leave empty
Node.js Version: 20.x or 22.x
```

## 3. Environment variables in Vercel

Add these in **Project Settings > Environment Variables**:

```text
BACKEND_URL=https://ai-saathi-1.onrender.com
NEXT_PUBLIC_SUPABASE_URL=<your Supabase project URL>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your Supabase anon key>
```

Optional, only if you use the built-in Google login route:

```text
GOOGLE_CLIENT_ID=<your Google OAuth client id>
GOOGLE_CLIENT_SECRET=<your Google OAuth client secret>
```

Do not set `NEXT_PUBLIC_API_URL` for the normal Vercel setup. With only `BACKEND_URL`, the app uses same-origin calls on Vercel and proxies `/study/*` plus `/health` to Render. That avoids browser CORS conflicts.

## 4. Render backend CORS

The current Render config already allows Vercel preview domains with:

```text
BACKEND_CORS_ORIGIN_REGEX=^https://.*\.vercel\.app$
```

After you get the final Vercel production URL, add it on Render for a stricter production allowlist:

```text
FRONTEND_ORIGIN=https://your-vercel-app.vercel.app
BACKEND_CORS_ORIGINS=https://your-vercel-app.vercel.app
```

Then redeploy the Render backend.

## 5. Deploy and test

Deploy on Vercel, then open:

```text
https://your-vercel-app.vercel.app/health
```

It should proxy to the Render backend health endpoint. Also test signup/login and a study-plan page, because those depend on Supabase public environment variables.

## 6. Local frontend test against Render

From the repository root:

```powershell
cd frontend
copy .env.example .env.local
```

Fill in the Supabase values in `frontend/.env.local`, then run:

```powershell
npm install
npm run build
npm run dev
```

Open:

```text
http://localhost:3000/health
```
