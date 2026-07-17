// termhop client — icon set (Lucide-style, matches the design system's icon guidance)
import React from 'react';

const base = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' };

export function BackIcon(props) {
  return <svg width="18" height="18" viewBox="0 0 24 24" {...base} {...props}><path d="m15 18-6-6 6-6" /></svg>;
}
export function DotsIcon(props) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" {...base} {...props}>
      <circle cx="12" cy="5" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="12" cy="19" r="1" />
    </svg>
  );
}
export function LockIcon(props) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" {...base} {...props}>
      <rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}
export function WarningIcon(props) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" {...base} {...props}>
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
      <path d="M12 9v4" /><path d="M12 17h.01" />
    </svg>
  );
}
export function BellIcon(props) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" {...base} {...props}>
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </svg>
  );
}
export function LaptopIcon(props) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" {...base} {...props}>
      <rect width="18" height="12" x="3" y="4" rx="2" ry="2" /><line x1="2" x2="22" y1="20" y2="20" />
    </svg>
  );
}
export function ChevronDownIcon(props) {
  return <svg width="13" height="13" viewBox="0 0 24 24" {...base} {...props}><path d="m6 9 6 6 6-6" /></svg>;
}
