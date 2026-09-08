import React from 'react'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'success'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', isLoading, disabled, children, ...props }, ref) => {
    const base = 'inline-flex items-center justify-center font-medium transition-all duration-150 rounded-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-dark-950 disabled:opacity-50 disabled:cursor-not-allowed select-none'
    
    const variants = {
      primary: 'bg-crimson-600 hover:bg-crimson-500 text-white shadow-lg shadow-crimson-900/30 focus:ring-crimson-500',
      secondary: 'bg-dark-800 hover:bg-dark-750 text-slate-200 border border-dark-700 hover:border-dark-600 focus:ring-slate-400',
      outline: 'border border-dark-700 hover:bg-dark-850 text-slate-300 hover:text-white focus:ring-slate-400',
      ghost: 'text-slate-400 hover:text-slate-100 hover:bg-dark-800/80 focus:ring-slate-400',
      danger: 'bg-red-900/80 hover:bg-red-800 text-red-200 border border-red-700/50 focus:ring-red-500',
      success: 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/30 focus:ring-emerald-500',
    }

    const sizes = {
      sm: 'text-xs px-2.5 py-1.5 gap-1.5',
      md: 'text-xs md:text-sm px-3.5 py-2 gap-2',
      lg: 'text-sm md:text-base px-5 py-2.5 gap-2.5',
    }

    return (
      <button
        ref={ref}
        className={twMerge(clsx(base, variants[variant], sizes[size], className))}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading && (
          <svg className="animate-spin -ml-0.5 mr-1.5 h-3.5 w-3.5 text-current" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        )}
        {children}
      </button>
    )
  }
)

Button.displayName = 'Button'
