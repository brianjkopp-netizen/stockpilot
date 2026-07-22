const PATHS = {
  signal: (
    <>
      <path d="M3 17 L9 11 L13 14 L21 6" />
      <path d="M15 6 L21 6 L21 12" />
    </>
  ),
  portfolio: (
    <>
      <rect x="3" y="6" width="18" height="14" />
      <path d="M3 10 L21 10" />
      <path d="M9 6 V4 H15 V6" />
    </>
  ),
  history: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7 V12 L15 14" />
    </>
  ),
  discover: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21 L16 16" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1A2 2 0 1 1 4.3 16.9l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1A2 2 0 1 1 7 4.3l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1A2 2 0 1 1 19.7 7l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
    </>
  ),
  refresh: (
    <>
      <path d="M21 12 a9 9 0 1 1 -3-6.7" />
      <path d="M21 4 V10 H15" />
    </>
  ),
  play: <path d="M6 4 L20 12 L6 20 Z" />,
  close: (
    <>
      <path d="M6 6 L18 18" />
      <path d="M18 6 L6 18" />
    </>
  ),
};

export default function Icon({ name, size = 16 }) {
  const glyph = PATHS[name];
  if (!glyph) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {glyph}
    </svg>
  );
}
