# Bounded — dashboard

The Next.js frontend for [Bounded](../README.md): five surfaces (Attacks,
Proof, Ledger, Mandate, Evidence) over the FastAPI backend in `../api/`.

See the [repo root README](../README.md) for what Bounded is, setup, and
architecture. This file only covers running the frontend on its own.

## Develop

```bash
npm install
npm run dev
```

Requires the API running at `http://127.0.0.1:8000` (or set
`NEXT_PUBLIC_API_BASE_URL`) — see the root README's setup section.

Open [http://localhost:3000](http://localhost:3000).
