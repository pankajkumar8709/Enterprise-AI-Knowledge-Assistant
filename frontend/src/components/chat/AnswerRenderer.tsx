import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

import type { Source } from '@/types/api';

import { CitationChip } from './CitationChip';

export interface AnswerRendererProps {
  text: string;
  sources: Source[];
  onOpen: (source: Source) => void;
}

/** Matches the `[S1]` markers the LLM emits (spec §10). */
const CITATION_PATTERN = /\[S(\d+)\]/g;

/**
 * Renders the answer as formatted Markdown and rewrites `[S#]` markers into
 * clickable citation chips. Messages loaded from history carry no sources, so
 * their markers are stripped rather than shown as raw text.
 */
export function AnswerRenderer({ text, sources, onOpen }: AnswerRendererProps) {
  const byRef = new Map(sources.map((source) => [source.ref, source]));
  const withLinks = sources.length
    ? text.replace(CITATION_PATTERN, (_match, n: string) => `[${n}](#cite-S${n})`)
    : text.replace(CITATION_PATTERN, '').replace(/[ \t]{2,}/g, ' ').trim();

  const components: Components = {
    a: ({ href, children }) => {
      const ref = href?.startsWith('#cite-') ? href.slice(6) : null;
      const source = ref ? byRef.get(ref) : undefined;
      if (!source) {
        return (
          <a href={href} target="_blank" rel="noreferrer noopener">
            {children}
          </a>
        );
      }
      return (
        <CitationChip source={source} onOpen={onOpen}>
          {children}
        </CitationChip>
      );
    },
    // Tables and long code stay inside the card.
    table: ({ children }) => (
      <div className="overflow-x-auto">
        <table>{children}</table>
      </div>
    ),
  };

  return (
    <div className="prose prose-sm prose-slate max-w-none prose-p:leading-6 prose-li:my-0.5">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {withLinks}
      </ReactMarkdown>
    </div>
  );
}
