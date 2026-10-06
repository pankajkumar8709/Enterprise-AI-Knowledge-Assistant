import type { HTMLAttributes, ReactNode, ThHTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

export function TableWrap({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn('w-full overflow-x-auto', className)}>
      <table className="w-full min-w-[640px] border-collapse text-sm">{children}</table>
    </div>
  );
}

export function THead({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <thead className={cn('bg-slate-50/80 text-left', className)}>
      <tr>{children}</tr>
    </thead>
  );
}

export function TH({ className, children, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope="col"
      className={cn('whitespace-nowrap px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500', className)}
      {...props}
    >
      {children}
    </th>
  );
}

export function TBody({ className, children }: { className?: string; children: ReactNode }) {
  return <tbody className={cn('divide-y divide-slate-100', className)}>{children}</tbody>;
}

export function TR({ className, children, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className={cn('transition-colors hover:bg-slate-50/70', className)} {...props}>
      {children}
    </tr>
  );
}

export function TD({ className, children, ...props }: HTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cn('px-4 py-3 align-middle text-slate-700', className)} {...props}>
      {children}
    </td>
  );
}
