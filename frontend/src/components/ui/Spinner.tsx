import { cn } from '@/lib/cn';

const sizes = {
  xs: 'h-3 w-3 border-[1.5px]',
  sm: 'h-4 w-4 border-2',
  md: 'h-5 w-5 border-2',
  lg: 'h-8 w-8 border-[3px]',
} as const;

export interface SpinnerProps {
  size?: keyof typeof sizes;
  className?: string;
  /** Accessible label for standalone spinners; inline spinners are hidden from AT. */
  label?: string;
}

export function Spinner({ size = 'sm', className, label }: SpinnerProps) {
  return (
    <span
      role={label ? 'status' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={cn(
        'inline-block shrink-0 animate-spin rounded-full border-current border-r-transparent align-[-0.125em]',
        sizes[size],
        className,
      )}
    />
  );
}
