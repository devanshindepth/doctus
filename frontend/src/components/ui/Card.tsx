import React from 'react'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export const Card: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <div
      className={twMerge(
        clsx(
          'glass-panel rounded-xl border border-dark-700/70 p-5 shadow-xl transition-all duration-150',
          className
        )
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <div
      className={twMerge(
        clsx('flex items-center justify-between pb-3 mb-4 border-b border-dark-750/80', className)
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  className,
  children,
  ...props
}) => {
  return (
    <h3
      className={twMerge(
        clsx('text-sm md:text-base font-semibold text-slate-100 flex items-center gap-2', className)
      )}
      {...props}
    >
      {children}
    </h3>
  )
}
