import { ArrowUpRight } from 'lucide-react';

import { SUGGESTIONS } from '@/lib/constants';

export function SuggestionCards({ onSelect }: { onSelect: (question: string) => void }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {SUGGESTIONS.map((suggestion) => (
        <button
          key={suggestion}
          type="button"
          onClick={() => onSelect(suggestion)}
          className="focus-ring group flex items-start justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-left text-sm font-medium text-slate-700 shadow-sm transition hover:border-indigo-200 hover:shadow-md"
        >
          <span>{suggestion}</span>
          <ArrowUpRight
            aria-hidden="true"
            className="mt-0.5 h-4 w-4 shrink-0 text-slate-300 transition group-hover:text-indigo-500"
          />
        </button>
      ))}
    </div>
  );
}
