import Link from 'next/link';
import { Card } from '@/components/ui';

export default function NotFound() {
  return (
    <Card className="card-pad">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="mt-1 text-sm text-ink-soft">That page or college does not exist in the loaded data.</p>
      <div className="mt-4 flex gap-2">
        <Link className="btn-primary" href="/">Back to predictor</Link>
        <Link className="btn-ghost" href="/colleges">Browse colleges</Link>
      </div>
    </Card>
  );
}
