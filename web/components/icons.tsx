/** Inline icons (no icon dependency). All are decorative: aria-hidden, sized by the caller. */
type P = { className?: string };
const base = 'h-4 w-4';
/** Builds an icon component from `|`-separated SVG paths. */
function svg(name: string, d: string) {
  const Icon = ({ className }: P) => (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinecap="round" strokeLinejoin="round" className={className ?? base}>
      {d.split('|').map((p, i) => <path key={i} d={p} />)}
    </svg>
  );
  Icon.displayName = name;
  return Icon;
}

export const IconTarget = svg('IconTarget', 'M12 3v3|M12 18v3|M3 12h3|M18 12h3|M12 12v0');
export const IconGauge = svg('IconGauge', 'M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4|M4 20a8 8 0 1 1 16 0|M12 10 15 7');
export const IconBuilding = svg('IconBuilding', 'M4 21V6a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v15|M15 21V10h3a2 2 0 0 1 2 2v9|M8 8h3|M8 12h3|M8 16h3|M2 21h20');
export const IconTable = svg('IconTable', 'M3 5h18v14H3z|M3 10h18|M9 10v9|M15 10v9');
export const IconBranch = svg('IconBranch', 'M6 3v6a3 3 0 0 0 3 3h6a3 3 0 0 1 3 3v3|M4 20h4|M16 2h4|M16 18h4');
export const IconInfo = svg('IconInfo', 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18|M12 11v5|M12 8v.5');
export const IconSearch = svg('IconSearch', 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14|M20 20l-4.2-4.2');
export const IconFilter = svg('IconFilter', 'M4 5h16|M7 12h10|M10 19h4');
export const IconPrint = svg('IconPrint', 'M7 8V3h10v5|M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2|M7 14h10v7H7z');
export const IconDownload = svg('IconDownload', 'M12 3v12|M8 11l4 4 4-4|M4 21h16');
export const IconUp = svg('IconUp', 'M12 19V5|M6 11l6-6 6 6');
export const IconDown = svg('IconDown', 'M12 5v14|M6 13l6 6 6-6');
export const IconArrowRight = svg('IconArrowRight', 'M5 12h14|M13 6l6 6-6 6');
export const IconShield = svg('IconShield', 'M12 3 5 6v6c0 4 3 7 7 9 4-2 7-5 7-9V6l-7-3z|M9 12l2 2 4-4');
export const IconDatabase = svg('IconDatabase', 'M12 3c4.4 0 8 1.1 8 2.5S16.4 8 12 8 4 6.9 4 5.5 7.6 3 12 3z|M20 5.5v13c0 1.4-3.6 2.5-8 2.5s-8-1.1-8-2.5v-13|M20 12c0 1.4-3.6 2.5-8 2.5S4 13.4 4 12');
export const IconLayers = svg('IconLayers', 'M12 3 3 8l9 5 9-5-9-5z|M3 14l9 5 9-5');
export const IconCheck = svg('IconCheck', 'M4 12l5 5L20 6');
export const IconClock = svg('IconClock', 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18|M12 7v5l3 2');
export const IconSort = svg('IconSort', 'M8 9l4-4 4 4|M8 15l4 4 4-4');
export const IconChevron = svg('IconChevron', 'M9 6l6 6-6 6');
