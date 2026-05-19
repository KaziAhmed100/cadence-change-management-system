# Cadence — frontend

Next.js 14 (App Router) UI for the Cadence change management system. See the [root README](../README.md) for project context.

## Requirements

- Node.js 18.17+
- The backend running (see [`../backend/README.md`](../backend/README.md))

## Local development

```bash
# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# edit .env.local — point NEXT_PUBLIC_API_BASE_URL at your backend

# Run the dev server (Phase 8 onwards)
npm run dev
```

## Design system

The cherry + white design tokens are defined in [`tailwind.config.ts`](./tailwind.config.ts). Don't introduce arbitrary colors in JSX — extend the config instead.

| Token            | Value     | Use                          |
| ---------------- | --------- | ---------------------------- |
| `cherry-500`     | `#DC143C` | Primary actions, brand       |
| `cherry-50`      | `#FFF0F3` | Subtle backgrounds, hovers   |
| `canvas`         | `#FAFAF9` | App background               |
| `surface`        | `#FFFFFF` | Cards, modals                |
| `ink-primary`    | `#1F1F1F` | Primary text                 |
| `ink-secondary`  | `#64748B` | Secondary text               |
| `status-success` | `#10B981` | Approved, success            |
| `status-warning` | `#F59E0B` | Pending, warning             |
| `status-danger`  | `#EF4444` | Rejected, failed             |

## Scripts

| Script           | What it does                |
| ---------------- | --------------------------- |
| `npm run dev`    | Start dev server on :3000   |
| `npm run build`  | Production build            |
| `npm run lint`   | ESLint                      |
| `npm run type-check` | TypeScript no-emit check |
| `npm run format` | Format with Prettier        |
