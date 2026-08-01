# Public Live Demo

This creates a public demo where the hosted page calls a live Predicate API.
For safety, the API uses sanitized fixture data instead of private DataHub.

## Architecture

```text
Netlify public page
  -> public Predicate Review API
     -> sanitized DataHub fixture JSON
```

This is live API-backed, but not connected to a private DataHub deployment.

## Deploy the API on Render

1. Push this repository to GitHub.
2. Open Render and create a new **Web Service**.
3. Choose the repository.
4. Render should detect `render.yaml`.
5. Deploy.
6. Copy the deployed service URL, for example:

```text
https://predicate-review-api.onrender.com
```

Test the API:

```bash
curl https://predicate-review-api.onrender.com/api/runs
```

You should see JSON with `runs`.

## Connect Netlify to the API

There are two safe options.

### Option 1: Query parameter

Open the public page with:

```text
https://leafy-maamoul-4acf4b.netlify.app/?api=https://predicate-review-api.onrender.com
```

This requires no code change after you know the API URL.

### Option 2: Hard-code the API URL

In `public-demo/index.html`, set:

```js
const PUBLIC_API_BASE = "https://predicate-review-api.onrender.com";
```

Then redeploy Netlify.

## What to Say

Use:

> The public page is live API-backed using sanitized DataHub fixture data. The
> local demo shows the same API connected to a real local DataHub quickstart.

Avoid:

> The public page is connected to our private local DataHub.

## Screenshot Checklist

- Public page showing `Mode: public API fixture`.
- Browser Network tab showing `/api/runs` from the Render API.
- API JSON at `/api/runs`.
- Local DataHub extension screenshot for the real DataHub-backed proof.
