import { zodResolver } from '@hookform/resolvers/zod';
import { CloudUpload, FileUp, Trash2 } from 'lucide-react';
import { useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Button } from '@/components/ui/Button';
import { FormField, Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Select } from '@/components/ui/Select';
import { Spinner } from '@/components/ui/Spinner';
import { useDepartmentsQuery } from '@/hooks/useAdmin';
import { useUploadDocument, validateUploadFile } from '@/hooks/useDocuments';
import { cn } from '@/lib/cn';
import { ACCEPTED_EXTENSIONS, ACCEPT_ATTRIBUTE, MAX_UPLOAD_BYTES, VISIBILITY_LABEL } from '@/lib/constants';
import { formatBytes } from '@/lib/format';

const uploadSchema = z
  .object({
    title: z.string().trim().min(1, 'A title is required').max(255, 'Title must be 255 characters or fewer'),
    visibility: z.enum(['all', 'department', 'admin_only']),
    department_ids: z.array(z.number()),
  })
  .refine((values) => values.visibility !== 'department' || values.department_ids.length > 0, {
    message: 'Select at least one department',
    path: ['department_ids'],
  });

type UploadValues = z.infer<typeof uploadSchema>;

export interface UploadModalProps {
  open: boolean;
  onClose: () => void;
}

/** `POST /documents` (multipart) — title, file, visibility and department ids. */
export function UploadModal({ open, onClose }: UploadModalProps) {
  const upload = useUploadDocument();
  const departments = useDepartmentsQuery();
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const prefilledTitle = useRef<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<UploadValues>({
    resolver: zodResolver(uploadSchema),
    defaultValues: { title: '', visibility: 'all', department_ids: [] },
  });

  const visibility = watch('visibility');
  const selectedDepartments = watch('department_ids');

  function acceptFile(candidate: File | null | undefined): void {
    if (!candidate) return;
    const problem = validateUploadFile(candidate, ACCEPTED_EXTENSIONS);
    if (problem) {
      setFileError(problem);
      setFile(null);
      return;
    }
    setFileError(null);
    setFile(candidate);
    const derived = candidate.name.replace(/\.[^.]+$/, '');
    const current = watch('title');
    if (!current || current === prefilledTitle.current) {
      setValue('title', derived, { shouldValidate: true });
      prefilledTitle.current = derived;
    }
  }

  function close(): void {
    if (upload.isPending) return;
    setFile(null);
    setFileError(null);
    prefilledTitle.current = null;
    reset({ title: '', visibility: 'all', department_ids: [] });
    onClose();
  }

  const submit = handleSubmit(async (values) => {
    if (!file) {
      setFileError('Choose a file to upload.');
      return;
    }
    await upload.mutateAsync({
      file,
      title: values.title.trim(),
      visibility: values.visibility,
      department_ids: values.visibility === 'department' ? values.department_ids : [],
    });
    close();
  });

  return (
    <Modal
      open={open}
      onClose={close}
      title="Upload document"
      description={`PDF, DOCX, PPTX, TXT or MD — up to ${formatBytes(MAX_UPLOAD_BYTES, 0)}.`}
      size="lg"
      dismissible={!upload.isPending}
      footer={
        <>
          <Button variant="secondary" onClick={close} disabled={upload.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="upload-form" loading={upload.isPending}>
            {upload.isPending ? 'Uploading…' : 'Upload and process'}
          </Button>
        </>
      }
    >
      <form id="upload-form" noValidate onSubmit={(event) => void submit(event)} className="space-y-4">
        <div>
          <span className="mb-1.5 block text-sm font-medium text-slate-700">File</span>
          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              acceptFile(event.dataTransfer.files[0]);
            }}
            className={cn(
              'flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-4 py-6 text-center transition',
              dragging ? 'border-indigo-400 bg-indigo-50/60' : 'border-slate-200 bg-slate-50/60',
              fileError ? 'border-rose-300' : '',
            )}
          >
            {file ? (
              <>
                <FileUp aria-hidden="true" className="h-5 w-5 text-indigo-600" />
                <p className="text-sm font-medium text-slate-800">{file.name}</p>
                <p className="text-xs text-slate-500">{formatBytes(file.size)}</p>
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<Trash2 aria-hidden="true" className="h-3.5 w-3.5" />}
                  onClick={() => {
                    setFile(null);
                    setFileError(null);
                  }}
                >
                  Remove
                </Button>
              </>
            ) : (
              <>
                <CloudUpload aria-hidden="true" className="h-6 w-6 text-slate-400" />
                <p className="text-sm text-slate-600">
                  Drag a file here, or{' '}
                  <button
                    type="button"
                    onClick={() => inputRef.current?.click()}
                    className="focus-ring rounded font-medium text-indigo-700 hover:underline"
                  >
                    browse
                  </button>
                </p>
                <p className="text-xs text-slate-500">.pdf .docx .pptx .txt .md</p>
              </>
            )}
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT_ATTRIBUTE}
              className="sr-only"
              aria-label="Choose a file to upload"
              onChange={(event) => acceptFile(event.target.files?.[0])}
            />
          </div>
          {fileError ? (
            <p role="alert" className="mt-1.5 text-xs font-medium text-rose-600">
              {fileError}
            </p>
          ) : null}
        </div>

        <FormField label="Title" error={errors.title?.message} required htmlFor="upload-title">
          <Input id="upload-title" placeholder="Leave Policy 2025" invalid={Boolean(errors.title)} {...register('title')} />
        </FormField>

        <FormField label="Who can see this document?" htmlFor="upload-visibility">
          <Select id="upload-visibility" {...register('visibility')}>
            <option value="all">{VISIBILITY_LABEL.all}</option>
            <option value="department">{VISIBILITY_LABEL.department}</option>
            <option value="admin_only">{VISIBILITY_LABEL.admin_only}</option>
          </Select>
        </FormField>

        {visibility === 'department' ? (
          <fieldset>
            <legend className="mb-1.5 text-sm font-medium text-slate-700">
              Departments
              <span className="ml-0.5 text-rose-600" aria-hidden="true">
                *
              </span>
            </legend>
            {departments.isPending ? (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Spinner /> Loading departments…
              </div>
            ) : !departments.data?.length ? (
              <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                No departments exist yet. Create one under Users → Departments first.
              </p>
            ) : (
              <div className="grid max-h-40 gap-1 overflow-y-auto rounded-xl border border-slate-200 p-2 sm:grid-cols-2">
                {departments.data.map((department) => {
                  const checked = selectedDepartments.includes(department.id);
                  return (
                    <label
                      key={department.id}
                      className={cn(
                        'focus-within:ring-2 focus-within:ring-indigo-500 flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition',
                        checked ? 'bg-indigo-50 text-indigo-800' : 'text-slate-700 hover:bg-slate-50',
                      )}
                    >
                      <input
                        type="checkbox"
                        value={department.id}
                        checked={checked}
                        className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                        onChange={(event) => {
                          const next = event.target.checked
                            ? [...selectedDepartments, department.id]
                            : selectedDepartments.filter((id) => id !== department.id);
                          setValue('department_ids', next, { shouldValidate: true });
                        }}
                      />
                      {department.name}
                    </label>
                  );
                })}
              </div>
            )}
            {errors.department_ids ? (
              <p role="alert" className="mt-1.5 text-xs font-medium text-rose-600">
                {errors.department_ids.message}
              </p>
            ) : null}
          </fieldset>
        ) : null}

        {upload.isPending ? (
          <p role="status" className="flex items-center gap-2 text-xs text-slate-500">
            <Spinner /> Uploading and queuing ingestion…
          </p>
        ) : null}
      </form>
    </Modal>
  );
}
