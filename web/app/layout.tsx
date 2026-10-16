import type { Metadata, Viewport } from 'next';
import { Inter } from 'next/font/google';
import Script from 'next/script';
import './globals.css';
import { Sidebar } from '@/components/shell';
import { getHealth, getYears } from '@/lib/api';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans', display: 'swap' });

/**
 * Google Analytics 4 measurement ID.
 *
 * Safe to keep in the repository: it is served in the page source of every visit, so it is public by
 * design. `NEXT_PUBLIC_GA_ID` overrides it, and setting that to an empty string switches analytics off.
 * It is read at build time, not run time, because NEXT_PUBLIC_ values are inlined into the client bundle.
 *
 * GA4's enhanced measurement counts page changes from History API events, which is how `next/link`
 * navigates, so client-side route changes are recorded without a manual pageview call.
 */
const GA_ID = process.env.NEXT_PUBLIC_GA_ID ?? 'G-296WHDE2K7';

export const metadata: Metadata = {
  title: 'NEET PG Counselling Intelligence',
  description: 'Historical MCC allotment cut-offs and a college predictor. Estimates only, not guarantees.',
  // Most visitors arrive on a phone, and the content is derived from official PDFs – keep it out of search.
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  // Deliberately no maximumScale / userScalable:false. Pinch-zoom is the main accessibility tool on a
  // phone for dense tables, and blocking it fails WCAG 1.4.4.
  themeColor: '#4f46e5',
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  let years: number[] = [];
  let dataVersion = 0;
  try {
    const [ys, health] = await Promise.all([getYears(), getHealth()]);
    years = ys.map((y) => y.year);
    dataVersion = health.data_version;
  } catch {
    /* API not reachable – the pages show their own error panels */
  }
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50
                                   focus:rounded-lg focus:bg-white focus:px-3 focus:py-2 focus:shadow-pop">
          Skip to content
        </a>
        {/*
          `lg:flex`, not `flex`. The Sidebar renders two siblings: the desktop rail (hidden below lg) and
          the mobile top bar (hidden from lg up). With a plain `flex` the mobile bar became a *column* in a
          horizontal row next to <main>, so below 1024px the bar consumed the width and the content was
          squeezed to a sliver or pushed off-screen entirely. Below lg this must be normal block flow.
        */}
        <div className="min-h-screen lg:flex">
          <Sidebar year={years[0] ?? 0} years={years} dataVersion={dataVersion} />
          <main id="main" className="min-w-0 flex-1 px-4 py-5 sm:px-6 lg:px-8">{children}</main>
        </div>

        {/*
          `next/script` rather than raw <script> tags: Next then owns the load order and keeps the
          loader out of the critical path. `afterInteractive` runs it once hydration is done, which is
          what Google's own snippet is for.
        */}
        {GA_ID ? (
          <>
            <Script src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`} strategy="afterInteractive" />
            <Script id="gtag-init" strategy="afterInteractive">
              {`window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '${GA_ID}');`}
            </Script>
          </>
        ) : null}
      </body>
    </html>
  );
}
