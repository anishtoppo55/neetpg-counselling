import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Sidebar } from '@/components/shell';
import { getHealth, getYears } from '@/lib/api';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans', display: 'swap' });

export const metadata: Metadata = {
  title: 'NEET PG Counselling Intelligence',
  description: 'Historical MCC allotment cut-offs and a college predictor. Estimates only, not guarantees.',
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
        <div className="flex min-h-screen">
          <Sidebar year={years[0] ?? 0} years={years} dataVersion={dataVersion} />
          <main id="main" className="min-w-0 flex-1 px-4 py-5 sm:px-6 lg:px-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
