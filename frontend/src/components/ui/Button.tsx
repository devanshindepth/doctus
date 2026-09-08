import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { LoaderCircle } from 'lucide-react'
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'success'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
}
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', isLoading, disabled, className = '', children, type = 'button', ...props }, ref,
) {
  return <button ref={ref} type={type} className={`button button-${variant} button-${size} ${className}`} disabled={disabled || isLoading} aria-busy={isLoading || undefined} {...props}>
    {isLoading && <LoaderCircle size={16} className="spin" aria-hidden="true" />}{children}
  </button>
})
