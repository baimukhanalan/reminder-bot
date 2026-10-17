import type { SVGProps } from 'react'

type Props = SVGProps<SVGSVGElement>
const base = { width: 24, height: 24, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }

export const HomeIcon = (props: Props) => <svg {...base} {...props}><path d="M3.5 10.5 12 3.7l8.5 6.8v9a1 1 0 0 1-1 1h-5v-6h-5v6h-5a1 1 0 0 1-1-1z" /></svg>
export const FolderIcon = (props: Props) => <svg {...base} {...props}><path d="M3 6.5h6l2 2h10v9.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><path d="M3 9h18" /></svg>
export const DatabaseIcon = (props: Props) => <svg {...base} {...props}><ellipse cx="12" cy="5" rx="7.5" ry="3" /><path d="M4.5 5v7c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3V5M4.5 12v7c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-7" /></svg>
export const BrainIcon = (props: Props) => <svg {...base} {...props}><path d="M9.5 4.7a3 3 0 0 0-5 2.2c0 .5.1.9.3 1.3A3.5 3.5 0 0 0 4 15a3 3 0 0 0 4.5 3.8A3 3 0 0 0 12 21V5.5a3 3 0 0 0-2.5-.8ZM14.5 4.7a3 3 0 0 1 5 2.2c0 .5-.1.9-.3 1.3A3.5 3.5 0 0 1 20 15a3 3 0 0 1-4.5 3.8A3 3 0 0 1 12 21" /><path d="M7 10a3 3 0 0 0 5 1.5M17 10a3 3 0 0 1-5 1.5" /></svg>
export const MicIcon = (props: Props) => <svg {...base} {...props}><rect x="8.5" y="3" width="7" height="12" rx="3.5" /><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3M9 21h6" /></svg>
export const SearchIcon = (props: Props) => <svg {...base} {...props}><circle cx="10.5" cy="10.5" r="6.5" /><path d="m15.5 15.5 5 5" /></svg>
export const PlusIcon = (props: Props) => <svg {...base} {...props}><path d="M12 5v14M5 12h14" /></svg>
export const NoteIcon = (props: Props) => <svg {...base} {...props}><path d="M6 3h9l4 4v14H6z" /><path d="M15 3v5h4M9 12h7M9 16h5" /></svg>
export const MoreIcon = (props: Props) => <svg {...base} {...props}><circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" /></svg>
export const ArrowIcon = (props: Props) => <svg {...base} {...props}><path d="m9 5 7 7-7 7" /></svg>
export const CloseIcon = (props: Props) => <svg {...base} {...props}><path d="m6 6 12 12M18 6 6 18" /></svg>

