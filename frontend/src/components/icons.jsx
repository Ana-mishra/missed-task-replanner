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

export const IconShield = (p) =>
  base(p, <>
    <path d="M8 1.8l4.5 1.7v3.7c0 3-1.9 5-4.5 6-2.6-1-4.5-3-4.5-6V3.5z" />
    <path d="M6 8l1.5 1.5L10.2 6.8" />
  </>);

export const IconMoon = (p) =>
  base(p, <path d="M13.5 10.5A5.5 5.5 0 015.5 2.5a5.5 5.5 0 008 8z" />);

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

export const IconUser = (p) =>
  base(p, <>
    <circle cx="8" cy="5" r="2.7" />
    <path d="M3 13.4c.6-2.7 2.6-4.2 5-4.2s4.4 1.5 5 4.2" />
  </>);

export const IconBellRing = (p) =>
  base(p, <>
    <path d="M8 2.8a4 4 0 014 4c0 2.9.7 3.7.7 3.7H3.3s.7-.8.7-3.7a4 4 0 014-4z" />
    <path d="M6.8 12.5a1.3 1.3 0 002.4 0" />
    <path d="M2.7 5.8c-.8 1.1-.8 2.5 0 3.6" />
    <path d="M13.3 5.8c.8 1.1.8 2.5 0 3.6" />
  </>);

export const IconPaintbrush = (p) =>
  base(p, <>
    <path d="M13.5 2.5L8.7 7.3" />
    <path d="M8.4 6.2l1.4 1.4L7 10.4 5.6 9z" />
    <path d="M5.6 9c-1.2 1.2-2 2.7-2.2 3.9-.1.5-.5.8-1 .8.1.5.5.9 1 .9 1.5-.1 3-1 4-2.2L5.6 9z" />
  </>);

export const IconPlanCalendar = (p) =>
  base(p, <>
    <rect x="3" y="3.5" width="10" height="9.5" rx="1.5" />
    <path d="M3 6.5h10M5.5 2v2.5M10.5 2v2.5" />
    <circle cx="5.8" cy="8.8" r="0.55" fill="currentColor" stroke="none" />
    <circle cx="8" cy="8.8" r="0.55" fill="currentColor" stroke="none" />
    <circle cx="10.2" cy="8.8" r="0.55" fill="currentColor" stroke="none" />
    <circle cx="5.8" cy="10.8" r="0.55" fill="currentColor" stroke="none" />
    <circle cx="8" cy="10.8" r="0.55" fill="currentColor" stroke="none" />
  </>);

export const IconChecklist = (p) =>
  base(p, <>
    <path d="M2.5 5.2l1.4 1.4 2.3-2.4" />
    <path d="M2.5 11.2l1.4 1.4 2.3-2.4" />
    <path d="M8.3 5.4h5.2" />
    <path d="M8.3 11.4h5.2" />
  </>);

export const IconSprout = (p) =>
  base(p, <>
    <path d="M8 13.5V8" />
    <path d="M8 8c0-2-1.5-3.2-3.7-3.2 0 2.2 1.5 3.2 3.7 3.2z" />
    <path d="M8 9.8c0-2 1.5-3.2 3.7-3.2 0 2.2-1.5 3.2-3.7 3.2z" />
  </>);

export const IconSliders = (p) =>
  base(p, <>
    <path d="M1.5 4.5h13" />
    <circle cx="10.5" cy="4.5" r="1.8" />
    <path d="M1.5 8h13" />
    <circle cx="5.5" cy="8" r="1.8" />
    <path d="M1.5 11.5h13" />
    <circle cx="11" cy="11.5" r="1.8" />
  </>);

export const IconLogout = (p) =>
  base(p, <>
    <path d="M9.5 2.5h-6v11h6" />
    <path d="M6 8h7.5M11.3 5.5L13.8 8l-2.5 2.5" />
  </>);

export const IconPencil = (p) =>
  base(p, <path d="M11.5 2.8a1.9 1.9 0 0 1 2.7 2.7L6 13.7l-3.2.8.8-3.2z" />);

export const IconTrash = (p) =>
  base(p, <>
    <path d="M2.5 4h11" />
    <path d="M6 4V3a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1" />
    <path d="M4.5 4l.6 8.2a1.5 1.5 0 0 0 1.5 1.3h2.8a1.5 1.5 0 0 0 1.5-1.3L11.5 4" />
    <path d="M6.5 6.5v4.5M9.5 6.5v4.5" />
  </>);

// Brand marks for OAuth buttons. Unlike the outline family above, these
// use their official fills: multicolor Google G, and the GitHub mark in
// currentColor so it adapts to light/dark themes. Decorative only.
export const IconGoogle = (p) => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    aria-hidden="true"
    {...p}
  >
    <path
      fill="#4285F4"
      d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z"
    />
    <path
      fill="#34A853"
      d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24z"
    />
    <path
      fill="#FBBC05"
      d="M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.98-3.09z"
    />
    <path
      fill="#EA4335"
      d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.98 3.09C6.22 6.86 8.87 4.75 12 4.75z"
    />
  </svg>
);

export const IconGitHub = (p) => (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
    {...p}
  >
    <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
  </svg>
);
