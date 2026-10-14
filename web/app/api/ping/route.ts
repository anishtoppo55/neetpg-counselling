import { NextResponse } from 'next/server';

/** Liveness probe for the container healthcheck (does not touch the API or database). */
export const dynamic = 'force-static';
export function GET() {
  return NextResponse.json({ status: 'ok' });
}
