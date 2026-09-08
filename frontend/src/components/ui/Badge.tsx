import React from 'react'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'success' | 'danger' | 'warning' | 'info' | 'neutral'
  size?: 'sm' | 'md'
}

export const Badge: React.FC<BadgeProps> = ({
  className,
  variant = 'neutral',
  size = 'sm',
  children,
  ...props
}) => {
  const base = 'inline-flex items-center font-semibold rounded border uppercase tracking-wider'

  const variants = {
    success: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    danger: 'bg-crimson-500/15 text-crimson-400 border-crimson-500/30',
    warning: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    info: 'bg-sky-500/15 text-sky-400 border-sky-500/30',
    neutral: 'bg-dark-800 text-slate-300 border-dark-700',
  }

  const sizes = {
    sm: 'text-[10px] px-2 py-0.5 gap-1',
    md: 'text-xs px-2.5 py-1 gap-1.5',
  }

  return (
    <span className={twMerge(clsx(base, variants[variant], sizes[size], className))} {...props}>
      {children}
    </span>
  )
}
