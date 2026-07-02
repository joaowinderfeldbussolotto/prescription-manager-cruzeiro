import { useId } from 'react'

// Olho estilizado, traço fino, gradiente dourado (mesma linguagem do logo.svg).
export default function Logo({ size = 30, strokeWidth = 2 }) {
  const gid = useId()
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden="true"
      role="img"
    >
      <defs>
        <linearGradient id={gid} x1="6" y1="10" x2="42" y2="38" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#E7C767" />
          <stop offset="0.5" stopColor="#D4AF37" />
          <stop offset="1" stopColor="#B8860B" />
        </linearGradient>
      </defs>
      <path
        d="M4 24 C 12 12, 36 12, 44 24 C 36 36, 12 36, 4 24 Z"
        stroke={`url(#${gid})`}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
      />
      <circle cx="24" cy="24" r="7.5" stroke={`url(#${gid})`} strokeWidth={strokeWidth} />
      <circle cx="24" cy="24" r="2.6" fill={`url(#${gid})`} />
    </svg>
  )
}
