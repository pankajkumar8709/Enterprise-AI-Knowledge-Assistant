import { Check, FileText, Sparkles, Trash2, Upload } from 'lucide-react';
import { useState } from 'react';

import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Drawer } from '@/components/ui/Drawer';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { FormField, Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { ProgressSteps } from '@/components/ui/ProgressSteps';
import { Select } from '@/components/ui/Select';
import { Skeleton, SkeletonTable } from '@/components/ui/Skeleton';
import { Spinner } from '@/components/ui/Spinner';
import { StatCard } from '@/components/ui/StatCard';
import { TD, TH, THead, TR, TableWrap, TBody } from '@/components/ui/Table';
import { TabPanel, Tabs } from '@/components/ui/Tabs';
import { Textarea } from '@/components/ui/Textarea';
import { Tooltip } from '@/components/ui/Tooltip';
import { toast } from '@/store/uiStore';

const BADGE_COLORS = ['slate', 'indigo', 'emerald', 'amber', 'rose', 'sky', 'violet'] as const;

/** `/dev/ui` — every design-system primitive on one page (spec §14 build order). */
export function DevUiPage() {
  const [tab, setTab] = useState('tokens');
  const [modalOpen, setModalOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 lg:p-8">
      <PageHeader
        title="Design system"
        description="Tokens and components used across the Phase 9 frontend."
        actions={
          <Button variant="secondary" onClick={() => (window.location.href = '/')}>
            Back to the app
          </Button>
        }
      />

      <Tabs
        items={[
          { id: 'tokens', label: 'Tokens' },
          { id: 'controls', label: 'Controls' },
          { id: 'feedback', label: 'Feedback' },
          { id: 'overlays', label: 'Overlays' },
        ]}
        value={tab}
        onChange={setTab}
      />

      <TabPanel id="tokens" active={tab === 'tokens'}>
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Typography</CardTitle>
            </CardHeader>
            <CardBody className="space-y-2">
              <p className="text-2xl font-semibold tracking-tight">Page title · text-2xl font-semibold</p>
              <p className="text-lg font-semibold">Section title · text-lg font-semibold</p>
              <p className="text-sm leading-6 text-slate-700">Body · text-sm leading-6 (Inter)</p>
              <p className="text-xs text-slate-500">Caption · text-xs text-slate-500</p>
              <p className="text-3xl font-bold tabular-nums">1,234 · text-3xl font-bold</p>
              <p className="font-mono text-sm">kb-2026-0001 · JetBrains Mono</p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Badges & status colours</CardTitle>
            </CardHeader>
            <CardBody className="flex flex-wrap gap-2">
              {BADGE_COLORS.map((color) => (
                <Badge key={color} color={color}>
                  {color}
                </Badge>
              ))}
              <Badge color="sky" dot={<span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-500" />}>
                processing
              </Badge>
            </CardBody>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2">
            <StatCard label="Documents ready" value="42" icon={<Check aria-hidden="true" className="h-5 w-5" />} tone="emerald" hint="+3 this week" />
            <StatCard label="Pending reviews" value="7" icon={<Sparkles aria-hidden="true" className="h-5 w-5" />} tone="amber" />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Progress steps</CardTitle>
            </CardHeader>
            <CardBody>
              <ProgressSteps
                steps={[
                  { key: 'extracting', label: 'Extracting' },
                  { key: 'cleaning', label: 'Cleaning' },
                  { key: 'chunking', label: 'Chunking' },
                  { key: 'embedding', label: 'Embedding' },
                  { key: 'okf', label: 'Facts' },
                  { key: 'indexing', label: 'Indexing' },
                ]}
                currentIndex={3}
              />
            </CardBody>
          </Card>
        </div>
      </TabPanel>

      <TabPanel id="controls" active={tab === 'controls'}>
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Buttons</CardTitle>
            </CardHeader>
            <CardBody className="flex flex-wrap items-center gap-2">
              <Button>Primary</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="danger">Danger</Button>
              <Button loading>Loading</Button>
              <Button size="sm" icon={<Upload aria-hidden="true" className="h-3.5 w-3.5" />}>
                Small
              </Button>
              <Button size="lg">Large</Button>
              <Tooltip content="Icon-only buttons always carry an aria-label">
                <Button size="icon" aria-label="Delete" variant="ghost" icon={<Trash2 aria-hidden="true" className="h-4 w-4" />} />
              </Tooltip>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Inputs</CardTitle>
            </CardHeader>
            <CardBody className="grid gap-4 sm:grid-cols-2">
              <FormField label="Text input" hint="Helper text sits below the control." htmlFor="dev-input">
                <Input id="dev-input" placeholder="Leave Policy 2025" />
              </FormField>
              <FormField label="With error" error="A title is required" htmlFor="dev-input-error">
                <Input id="dev-input-error" invalid defaultValue="" />
              </FormField>
              <FormField label="Select" htmlFor="dev-select">
                <Select id="dev-select" defaultValue="all">
                  <option value="all">All employees</option>
                  <option value="department">Specific departments</option>
                  <option value="admin_only">Admins only</option>
                </Select>
              </FormField>
              <FormField label="Textarea" htmlFor="dev-textarea">
                <Textarea id="dev-textarea" rows={3} placeholder="Multi-line input" />
              </FormField>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Table</CardTitle>
            </CardHeader>
            <CardBody className="p-0">
              <TableWrap>
                <THead>
                  <TH>Document</TH>
                  <TH>Status</TH>
                  <TH className="text-right">Chunks</TH>
                </THead>
                <TBody>
                  <TR>
                    <TD className="font-medium text-slate-900">Leave Policy 2025</TD>
                    <TD>
                      <Badge color="emerald">ready</Badge>
                    </TD>
                    <TD className="text-right tabular-nums">128</TD>
                  </TR>
                  <TR>
                    <TD className="font-medium text-slate-900">Onboarding Handbook</TD>
                    <TD>
                      <Badge color="sky" dot={<span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-500" />}>
                        processing
                      </Badge>
                    </TD>
                    <TD className="text-right tabular-nums">—</TD>
                  </TR>
                </TBody>
              </TableWrap>
            </CardBody>
          </Card>
        </div>
      </TabPanel>

      <TabPanel id="feedback" active={tab === 'feedback'}>
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Loading, empty and error states</CardTitle>
            </CardHeader>
            <CardBody className="space-y-4">
              <div className="flex items-center gap-3">
                <Spinner />
                <Skeleton className="h-4 w-48" />
              </div>
              <SkeletonTable rows={2} />
              <EmptyState
                icon={<FileText aria-hidden="true" className="h-5 w-5" />}
                title="Nothing here yet"
                hint="Empty states always pair an icon with a next step."
                action={<Button size="sm">Upload a document</Button>}
              />
              <ErrorState message="The list could not be loaded." onRetry={() => toast.info('Retried')} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Toasts</CardTitle>
            </CardHeader>
            <CardBody className="flex flex-wrap gap-2">
              <Button variant="secondary" onClick={() => toast.success('Document uploaded', 'Leave Policy 2025')}>
                Success
              </Button>
              <Button variant="secondary" onClick={() => toast.error('Upload failed', 'File is larger than 25 MB.')}>
                Error
              </Button>
              <Button variant="secondary" onClick={() => toast.info('Heads up', 'Review queue is empty.')}>
                Info
              </Button>
            </CardBody>
          </Card>
        </div>
      </TabPanel>

      <TabPanel id="overlays" active={tab === 'overlays'}>
        <Card>
          <CardHeader>
            <CardTitle>Overlays</CardTitle>
          </CardHeader>
          <CardBody className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setModalOpen(true)}>
              Open modal
            </Button>
            <Button variant="secondary" onClick={() => setDrawerOpen(true)}>
              Open drawer
            </Button>
            <Button variant="secondary" onClick={() => setConfirmOpen(true)}>
              Confirm dialog
            </Button>
          </CardBody>
        </Card>
      </TabPanel>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Modal title"
        description="Focus is trapped while this dialog is open."
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => setModalOpen(false)}>Save</Button>
          </>
        }
      >
        <p className="text-sm text-slate-600">Modal body content.</p>
      </Modal>

      <Drawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title="Drawer title"
        description="Right-hand panel, full width on mobile."
      >
        <p className="text-sm text-slate-600">Drawer body content.</p>
      </Drawer>

      <ConfirmDialog
        open={confirmOpen}
        title="Delete document"
        message="This removes the file, its chunks and every fact derived from it."
        confirmLabel="Delete"
        onConfirm={() => setConfirmOpen(false)}
        onClose={() => setConfirmOpen(false)}
      />
    </div>
  );
}
