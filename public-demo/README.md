# Predicate Public Demo

This folder is a sanitized version of the Predicate Review UI. It can run in
two public-safe modes:

- Static fallback data when no API is configured.
- Live public Predicate API calls when `?api=` or `PUBLIC_API_BASE` is set.

Deploy `public-demo/index.html` with any static host:

- GitHub Pages
- Netlify
- Vercel static output
- Cloudflare Pages
- an internal demo portal

This hosted page does not contain private DataHub URLs or tokens.

To connect a public fixture-backed API without editing the file, open:

```text
https://your-netlify-site.netlify.app/?api=https://your-predicate-api.onrender.com
```

For the local DataHub-backed UI, run `scripts/serve_review.py`.
