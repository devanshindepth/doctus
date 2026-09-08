import type { HTMLAttributes } from 'react'
export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'success' | 'danger' | 'warning' | 'info' | 'neutral'
  size?: 'sm' | 'md'
}
export function Badge({ variant = 'neutral', size = 'sm', className = '', children, ...props }: BadgeProps) {
  return <span className={`badge badge-${variant} badge-${size} ${className}`} {...props}>{children}</span>
}
