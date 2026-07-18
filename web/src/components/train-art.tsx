export function TrainArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 420 120" role="img" aria-label="Minh họa đoàn tàu Âu Lạc" className={className}>
      <defs>
        <linearGradient id="ta-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#FFFFFF" />
          <stop offset="1" stopColor="#DCE9F8" />
        </linearGradient>
      </defs>
      <path d="M30 92 L48 60 Q54 50 66 50 L330 50 Q374 50 396 78 Q404 88 392 92 Z" fill="url(#ta-body)" stroke="#082B5C" strokeWidth="2.5" />
      <path d="M330 50 Q374 50 396 78 Q404 88 392 92 L340 92 Z" fill="#082B5C" />
      <path d="M40 78 L388 78 Q394 84 390 86 L36 86 Z" fill="#E5484D" />
      {[78, 118, 158, 198, 238, 278].map((x) => (
        <rect key={x} x={x} y="58" width="26" height="13" rx="4" fill="#1261C9" opacity="0.85" />
      ))}
      <rect x="318" y="58" width="20" height="13" rx="4" fill="#EAF3FF" />
      <line x1="12" y1="100" x2="408" y2="100" stroke="#082B5C" strokeWidth="2.5" strokeLinecap="round" />
      {[30, 70, 110, 150, 190, 230, 270, 310, 350, 390].map((x) => (
        <line key={x} x1={x} y1="97" x2={x - 8} y2="103" stroke="#8FB3DE" strokeWidth="2" />
      ))}
    </svg>
  );
}
