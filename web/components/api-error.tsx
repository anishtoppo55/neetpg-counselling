import { ApiError, PUBLIC_BASE } from '@/lib/api';
import { Card, Notice } from './ui';

/** Renders a 422 from the API as a readable panel (field + allowed values) instead of a stack trace. */
export function ApiErrorPanel({ error, title = 'That combination cannot be answered' }:
  { error: unknown; title?: string }) {
  if (error instanceof ApiError) {
    const allowed = error.detail.allowed;
    return (
      <Card className="card-pad">
        <h2 className="text-base font-semibold">{title}</h2>
        <p className="mt-1 text-sm text-ink-soft">{error.detail.message}</p>
        {error.detail.field ? (
          <p className="mt-2 text-xs text-ink-faint">Field: <code className="rounded bg-slate-100 px-1">{error.detail.field}</code></p>
        ) : null}
        {allowed ? (
          <div className="mt-3">
            <p className="text-xs font-medium text-ink-soft">Supported values</p>
            <ul className="mt-1 flex flex-wrap gap-1.5">
              {(Array.isArray(allowed) ? allowed.map((a) => [String(a), ''] as const)
                : Object.entries(allowed as Record<string, string>)).map(([k, v]) => (
                <li key={k} className="chip bg-slate-100 text-ink-soft" title={v || undefined}>{k}{v ? ` – ${v}` : ''}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </Card>
    );
  }
  // Tailor the hint: on the Docker network the API container is probably down; with an external base URL
  // it is usually misconfigured or unreachable.
  const base = typeof window === 'undefined'
    ? (process.env.API_BASE_INTERNAL ?? 'http://api:8000')
    : PUBLIC_BASE;
  const isLocal = /localhost|127\.0\.0\.1|:\/\/api:/.test(base);
  return (
    <Card className="card-pad">
      <h2 className="text-base font-semibold">{title}</h2>
      <Notice tone="warn">
        {isLocal ? (
          <p>The API did not respond at <code className="rounded bg-white/60 px-1">{base}</code>. Start it with{' '}
            <code className="rounded bg-white/60 px-1">docker compose up -d api</code>, then reload this page.</p>
        ) : (
          <>
            <p>The API did not respond at <code className="rounded bg-white/60 px-1">{base}</code>.</p>
            <ul className="mt-1 list-disc pl-5 text-xs opacity-90">
              <li>Check <code className="rounded bg-white/60 px-1">API_BASE_INTERNAL</code> points at an address this
                server can actually reach.</li>
              <li>Check the API is running and its <code className="rounded bg-white/60 px-1">/api/live</code> returns 200.</li>
              <li>If the API sits behind a proxy or firewall, confirm the route and port are open.</li>
            </ul>
          </>
        )}
        <p className="mt-1 text-xs opacity-80">{error instanceof Error ? error.message : String(error)}</p>
      </Notice>
    </Card>
  );
}
