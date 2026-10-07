import {
  BookOpen,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  Library,
  MessagesSquare,
  ScrollText,
  ShieldCheck,
  Users,
} from 'lucide-react';
import type { ComponentType } from 'react';
import { NavLink } from 'react-router-dom';

import { cn } from '@/lib/cn';
import { APP_NAME, ROUTES } from '@/lib/constants';
import { useAuth } from '@/hooks/useAuth';

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string; 'aria-hidden'?: boolean | 'true' | 'false' }>;
  end?: boolean;
}

const EMPLOYEE_ITEMS: NavItem[] = [
  { to: ROUTES.chat, label: 'Chat', icon: MessagesSquare },
  { to: ROUTES.library, label: 'Library', icon: Library },
];

const ADMIN_ITEMS: NavItem[] = [
  { to: ROUTES.dashboard, label: 'Dashboard', icon: LayoutDashboard },
  { to: ROUTES.documents, label: 'Documents', icon: FileText, end: true },
  { to: ROUTES.knowledge, label: 'Knowledge', icon: BookOpen, end: true },
  { to: ROUTES.knowledgeReview, label: 'Review queue', icon: ClipboardCheck },
  { to: ROUTES.users, label: 'Users', icon: Users },
  { to: ROUTES.auditLogs, label: 'Audit logs', icon: ScrollText },
];

function NavSection({
  title,
  items,
  onNavigate,
  compact,
}: {
  title: string;
  items: NavItem[];
  onNavigate?: () => void;
  compact: boolean;
}) {
  return (
    <div className="space-y-1">
      <p className={cn('px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400', compact && 'lg:block hidden')}>
        {title}
      </p>
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end ?? false}
          onClick={onNavigate}
          title={compact ? item.label : undefined}
          className={({ isActive }) =>
            cn(
              'focus-ring flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition',
              'justify-center lg:justify-start',
              isActive
                ? 'bg-indigo-50 text-indigo-700'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
            )
          }
        >
          <item.icon aria-hidden="true" className="h-4 w-4 shrink-0" />
          <span className={cn('truncate', compact ? 'hidden lg:inline' : 'inline')}>{item.label}</span>
        </NavLink>
      ))}
    </div>
  );
}

export interface SidebarProps {
  /** Compact mode collapses labels to an icon rail below `lg`. */
  compact?: boolean;
  onNavigate?: () => void;
  className?: string;
}

export function Sidebar({ compact = false, onNavigate, className }: SidebarProps) {
  const { isAdmin } = useAuth();

  return (
    <nav aria-label="Main navigation" className={cn('flex h-full flex-col gap-6 overflow-y-auto p-3', className)}>
      <div className={cn('flex items-center gap-2 px-3 pt-2', compact && 'justify-center lg:justify-start')}>
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white">
          <ShieldCheck aria-hidden="true" className="h-4 w-4" />
        </span>
        <span className={cn('text-sm font-semibold text-slate-900', compact ? 'hidden lg:inline' : 'inline')}>
          {APP_NAME}
        </span>
      </div>

      <NavSection title="Assistant" items={EMPLOYEE_ITEMS} compact={compact} {...(onNavigate ? { onNavigate } : {})} />
      {isAdmin ? (
        <NavSection title="Administration" items={ADMIN_ITEMS} compact={compact} {...(onNavigate ? { onNavigate } : {})} />
      ) : null}

      <div className="mt-auto px-3 pb-2">
        <p className={cn('text-[11px] leading-4 text-slate-400', compact ? 'hidden lg:block' : 'block')}>
          v0.9.0
        </p>
      </div>
    </nav>
  );
}
