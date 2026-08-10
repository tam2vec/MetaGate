# Public API Demo

The hosted page calls the MetaGate API by default. The API has two explicit
modes: `fixture` for a safe public fallback, and `live` for a real DataHub
deployment. It never presents fixture data as live DataHub evidence.

The public fixture includes the positive control, blocked proof assets, and
showcase records for NYC Taxi, Healthcare, and Fiction Retail. Those showcase
records are labelled fixture representations; they do not claim that Render
can reach the local DataHub catalog.

## Architecture

```text
Netlify public page
  -> MetaGate API on Render
     -> DataHub GraphQL (live mode) OR labelled fixture (fixture mode)
```

Render cannot reach `http://localhost:8080` on your Mac. Live hosted mode
requires a reachable DataHub GraphQL URL and a server-side token.

This repository includes `render.live.yaml` for the live service variant. Use
it only after you have permissioned, non-sensitive DataHub access. The default
`render.yaml` deliberately stays in fixture mode so a public deployment cannot
accidentally expose a private DataHub or fail closed because no credentials were
provided.

## Deploy the API on Render

1. Push this repository to GitHub.
2. Open Render and create a new **Web Service**.
3. Choose the repository.
4. Render should detect `render.yaml`.
5. Deploy.
6. Copy the deployed service URL, for example:

```text
https://predicate-ixz0.onrender.com
```

Test the API:

```bash
curl https://predicate-ixz0.onrender.com/api/runs
```

You should see JSON with `runs`.

## Switch Render to real DataHub

Only do this after you have a reachable DataHub deployment. In Render, set:

```text
METAGATE_DEMO_MODE=live
DATAHUB_GRAPHQL_URL=https://your-datahub-host/api/graphql
DATAHUB_TOKEN=<read-only-token>
```

`DATAHUB_TOKEN` is a secret environment variable. Never put it in Netlify or
the browser URL. Redeploy Render, then verify the source before presenting it:

```bash
curl -s https://predicate-ixz0.onrender.com/api/status | python3 -m json.tool
curl -s https://predicate-ixz0.onrender.com/api/runs | python3 -m json.tool
```

The status must say `"mode": "live-datahub-api"`, `"live_datahub": true`,
and `"fixture_fallback_blocked": true`. The runs response must say
`"source": "live-api"`. If it says `fixture-api`, the public demo is not
connected to DataHub yet.

## Connect Netlify to the API

There are two safe options.

### Option 1: Query parameter

Open the public page with:

```text
https://leafy-maamoul-4acf4b.netlify.app/?api=https://predicate-ixz0.onrender.com
```

The current page already uses this Render API by default; the query parameter
is useful when testing another API.

### Option 2: Hard-code the API URL

In `public-demo/index.html`, set:

```js
const PUBLIC_API_BASE = "https://predicate-ixz0.onrender.com";
```

Then redeploy Netlify.

## What to Say

Use:

When Render is still in fixture mode:

> The public page is API-backed and explicitly labelled fixture data. The real
> DataHub proof runs locally against GraphQL.

After the status check passes in live mode:

> The public page calls MetaGate on every load; MetaGate reads this DataHub
> GraphQL deployment and blocks fixture fallback.

Avoid:

> The public page is connected to our private local DataHub.

## Screenshot Checklist

- Public page showing `Mode: live DataHub API`.
- Render `/api/status` showing `live_datahub: true` and fixture fallback blocked.
- Browser Network tab showing `/api/runs` from the Render API.
- API JSON at `/api/runs`.
- DataHub asset screenshot with the same URN as the API result.
