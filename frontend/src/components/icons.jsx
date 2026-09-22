// Single consistent outline icon family for the Day Sheet prototype.
// 1.5px stroke, currentColor, 16px viewBox. No emoji, no mixed glyph sets.
function base(props, children) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export const IconClock = (p) =>
  base(p, <>
    <circle cx="8" cy="8" r="6" />
    <path d="M8 4.5V8l2.5 1.5" />
  </>);

export const IconMissed = (p) =>
  base(p, <>
    <circle cx="8" cy="8" r="6" />
    <path d="M4 4l8 8" />
  </>);

export const IconOverdue = (p) =>
  base(p, <>
    <path d="M8 2.5a5.5 5.5 0 015.5 5.5c0 4 1 5 1 5H1.5s1-1 1-5A5.5 5.5 0 018 2.5z" />
    <path d="M6.5 15a1.5 1.5 0 003 0" />
  </>);

export const IconBell = (p) =>
  base(p, <>
    <path d="M8 2.5a5.5 5.5 0 015.5 5.5c0 4 1 5 1 5H1.5s1-1 1-5A5.5 5.5 0 018 2.5z" />
    <path d="M6.5 15a1.5 1.5 0 003 0" />
  </>);

export const IconCheck = (p) => base(p, <path d="M3 8.5l3.5 3.5L13 4.5" />);

export const IconCalendar = (p) =>
  base(p, <>
    <rect x="2.5" y="3.5" width="11" height="10" rx="1.5" />
    <path d="M2.5 6.5h11M5.5 2v3M10.5 2v3" />
  </>);

export const IconEnergy = (p) => base(p, <path d="M9 1.5L3.5 9H8l-1 5.5L12.5 7H8l1-5.5z" />);

export const IconFlag = (p) =>
  base(p, <>
    <path d="M4 14V2.5" />
    <path d="M4 3h8.5L10.5 6l2 3H4" />
  </>);

export const IconRecover = (p) =>
  base(p, <>
    <path d="M13.5 8a5.5 5.5 0 11-1.6-3.9" />
    <path d="M13.5 1.5v3h-3" />
  </>);

export const IconChevron = (p) => base(p, <path d="M6 3.5L10.5 8 6 12.5" />);

export const IconClose = (p) => base(p, <path d="M4 4l8 8M12 4l-8 8" />);

export const IconPlus = (p) => base(p, <path d="M8 3v10M3 8h10" />);

export const IconList = (p) =>
  base(p, <>
    <path d="M5.5 4.5h8M5.5 8h8M5.5 11.5h8" />
    <circle cx="2.8" cy="4.5" r="0.4" />
    <circle cx="2.8" cy="8" r="0.4" />
    <circle cx="2.8" cy="11.5" r="0.4" />
  </>);

export const IconLeaf = (p) =>
  base(p, <>
    <path d="M12.5 3.5C8 3.5 4.5 7 4.5 11.5c4.5 0 8-3.5 8-8z" />
    <path d="M4.5 11.5C6 9 8 7 10.5 5.5" />
  </>);

export const IconNote = (p) =>
  base(p, <>
    <path d="M4 2.5h6l2.5 2.5v8.5h-8.5v-11z" />
    <path d="M10 2.5v2.5h2.5M6 8h4M6 10.5h4" />
  </>);

export const IconSun = (p) =>
  base(p, <>
    <circle cx="8" cy="8" r="3" fill="currentColor" stroke="none" />
    <path d="M8 1.5v1.8M8 12.7v1.8M1.5 8h1.8M12.7 8h1.8M3.4 3.4l1.3 1.3M11.3 11.3l1.3 1.3M12.6 3.4l-1.3 1.3M4.7 11.3l-1.3 1.3" />
  </>);

export const IconCalendarCheck = (p) =>
  base(p, <>
    <rect x="2.5" y="3.5" width="11" height="10" rx="1.5" />
    <path d="M2.5 6.5h11M5.5 2v3M10.5 2v3" />
    <path d="M6.3 10.3l1.7 1.7 3-3.4" />
  </>);

export const IconCalendarClock = (p) =>
  base(p, <>
    <rect x="2.5" y="3.5" width="11" height="10" rx="1.5" />
    <path d="M2.5 6.5h11M5.5 2v3M10.5 2v3" />
    <circle cx="8" cy="10.1" r="2.4" />
    <path d="M8 8.9v1.2l1.2 0.8" />
  </>);

export const IconHistory = (p) =>
  base(p, <>
    <path d="M13.5 8a5.5 5.5 0 11-1.6-3.9" />
    <path d="M13.5 1.5v3h-3" />
    <path d="M8 5.5V8l1.8 1.2" />
  </>);

export const IconStats = (p) =>
  base(p, <>
    <rect x="2.6" y="9" width="2.6" height="4.5" rx="1.3" fill="currentColor" stroke="none" />
    <rect x="6.7" y="6" width="2.6" height="7.5" rx="1.3" fill="currentColor" stroke="none" />
    <rect x="10.8" y="3" width="2.6" height="10.5" rx="1.3" fill="currentColor" stroke="none" />
  </>);

export const IconJournal = (p) =>
  base(p, <>
    <path d="M8 4.8C6.6 3.9 4.9 3.6 3.2 3.9v7.6c1.7-.3 3.4 0 4.8.9 1.4-.9 3.1-1.2 4.8-.9V3.9c-1.7-.3-3.4 0-4.8.9z" />
    <path d="M8 4.8v7.6" />
    <path d="M8 10.2c-.2-1.6.3-2.9 1.6-3.7.4 1.5-.1 2.9-1.6 3.7z" />
    <path d="M12 1.3v1.6M11.2 2.1h1.6" />
  </>);
