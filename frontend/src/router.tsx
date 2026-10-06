import { createBrowserRouter } from 'react-router-dom';

import { AppShell } from '@/components/layout/AppShell';
import { RequireAuth } from '@/components/layout/RequireAuth';
import { RequireRole } from '@/components/layout/RequireRole';
import { ChatPage } from '@/pages/app/Chat';
import { LibraryPage } from '@/pages/app/Library';
import { AuditLogsPage } from '@/pages/admin/AuditLogs';
import { DashboardPage } from '@/pages/admin/Dashboard';
import { DocumentDetailPage } from '@/pages/admin/DocumentDetail';
import { DocumentsPage } from '@/pages/admin/Documents';
import { KnowledgeDetailPage } from '@/pages/admin/KnowledgeDetail';
import { KnowledgeListPage } from '@/pages/admin/KnowledgeList';
import { KnowledgeReviewPage } from '@/pages/admin/KnowledgeReview';
import { UsersPage } from '@/pages/admin/Users';
import { DevUiPage } from '@/pages/DevUi';
import { HomeRedirect } from '@/pages/HomeRedirect';
import { LoginPage } from '@/pages/Login';
import { NotFoundPage } from '@/pages/NotFound';
import { SignupPage } from '@/pages/Signup';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/signup', element: <SignupPage /> },
  { path: '/dev/ui', element: <DevUiPage /> },

  {
    element: <RequireAuth />,
    children: [
      { index: true, path: '/', element: <HomeRedirect /> },
      {
        element: <AppShell />,
        children: [
          { path: '/app/chat', element: <ChatPage /> },
          { path: '/app/chat/:conversationId', element: <ChatPage /> },
          { path: '/app/documents', element: <LibraryPage /> },

          {
            element: <RequireRole role="admin" />,
            children: [
              { path: '/admin/dashboard', element: <DashboardPage /> },
              { path: '/admin/documents', element: <DocumentsPage /> },
              { path: '/admin/documents/:documentId', element: <DocumentDetailPage /> },
              { path: '/admin/knowledge', element: <KnowledgeListPage /> },
              { path: '/admin/knowledge/review', element: <KnowledgeReviewPage /> },
              { path: '/admin/knowledge/:knowledgeId', element: <KnowledgeDetailPage /> },
              { path: '/admin/users', element: <UsersPage /> },
              { path: '/admin/audit-logs', element: <AuditLogsPage /> },
            ],
          },

          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },

  { path: '*', element: <NotFoundPage /> },
]);
