import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Button } from '@/components/ui/Button';
import { FormField, Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Select } from '@/components/ui/Select';
import { Spinner } from '@/components/ui/Spinner';
import { Textarea } from '@/components/ui/Textarea';
import { useDepartmentsQuery } from '@/hooks/useAdmin';
import { useCreateKnowledge, useUpdateKnowledge } from '@/hooks/useKnowledge';
import { cn } from '@/lib/cn';
import { OKF_FIELD_SPECS, OKF_TYPE_LABEL, OKF_TYPE_ORDER, VISIBILITY_LABEL } from '@/lib/constants';
import type { OkfObjectDto, OkfType } from '@/types/api';
import type { OkfFieldSpec } from '@/types/domain';

export interface OkfFormProps {
  open: boolean;
  onClose: () => void;
  /** Present when editing an existing object (requires a change note). */
  object?: OkfObjectDto | null;
  /** Defaults to `policy` when creating from the list page. */
  defaultType?: OkfType;
}

function buildSchema(mode: 'create' | 'edit') {
  return z
    .object({
      object_type: z.enum(['policy', 'employee', 'department', 'product', 'faq', 'business_rule', 'asset']),
      name: z.string().trim().min(1, 'A name is required').max(255, 'Keep the name under 255 characters'),
      summary: z.string().trim().max(2000, 'Keep the summary under 2000 characters').optional(),
      visibility: z.enum(['all', 'department', 'admin_only']),
      department_ids: z.array(z.number()),
      change_note: z.string().trim().max(1000).optional(),
    })
    .refine((values) => values.visibility !== 'department' || values.department_ids.length > 0, {
      message: 'Select at least one department',
      path: ['department_ids'],
    })
    .refine((values) => mode === 'create' || Boolean(values.change_note?.trim()), {
      message: 'A change note is required so the version history explains the edit',
      path: ['change_note'],
    });
}

type FormValues = z.infer<ReturnType<typeof buildSchema>>;

function toFieldValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) return value.map((item) => toFieldValue(item)).join(', ');
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

/**
 * Metadata + `payload` editor for a knowledge object. The plan's
 * `GET /knowledge/schema` endpoint does not exist, so the per-type field list
 * comes from `OKF_FIELD_SPECS` (spec §6.2).
 */
export function OkfForm({ open, onClose, object = null, defaultType = 'policy' }: OkfFormProps) {
  const mode: 'create' | 'edit' = object ? 'edit' : 'create';
  const schema = useMemo(() => buildSchema(mode), [mode]);
  const create = useCreateKnowledge();
  const update = useUpdateKnowledge(object?.id ?? 0);
  const departments = useDepartmentsQuery();
  const [payloadValues, setPayloadValues] = useState<Record<string, string>>({});
  const [payloadErrors, setPayloadErrors] = useState<Record<string, string>>({});

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      object_type: object?.object_type ?? defaultType,
      name: object?.name ?? '',
      summary: object?.summary ?? '',
      visibility: object?.visibility ?? 'all',
      department_ids: object?.department_ids ?? [],
      change_note: '',
    },
  });

  const objectType = watch('object_type');
  const visibility = watch('visibility');
  const selectedDepartments = watch('department_ids');
  const fields = OKF_FIELD_SPECS[objectType];

  // Re-seed the payload editor whenever the modal opens or the type changes.
  useEffect(() => {
    if (!open) return;
    reset({
      object_type: object?.object_type ?? defaultType,
      name: object?.name ?? '',
      summary: object?.summary ?? '',
      visibility: object?.visibility ?? 'all',
      department_ids: object?.department_ids ?? [],
      change_note: '',
    });
    setPayloadErrors({});
    setPayloadValues(() => {
      const seeded: Record<string, string> = {};
      for (const field of OKF_FIELD_SPECS[object?.object_type ?? defaultType]) {
        seeded[field.key] = toFieldValue(object?.payload?.[field.key]);
      }
      return seeded;
    });
  }, [defaultType, object, open, reset]);

  function switchType(next: OkfType): void {
    setValue('object_type', next, { shouldValidate: true });
    setPayloadValues(() => {
      const seeded: Record<string, string> = {};
      for (const field of OKF_FIELD_SPECS[next]) seeded[field.key] = '';
      return seeded;
    });
    setPayloadErrors({});
  }

  function validatePayload(): Record<string, unknown> | null {
    const nextErrors: Record<string, string> = {};
    const payload: Record<string, unknown> = {};
    for (const field of fields) {
      const raw = (payloadValues[field.key] ?? '').trim();
      if (!raw) {
        if (field.required) nextErrors[field.key] = `${field.label} is required`;
        continue;
      }
      payload[field.key] = field.type === 'array' ? raw.split(',').map((item) => item.trim()).filter(Boolean) : raw;
    }
    setPayloadErrors(nextErrors);
    return Object.keys(nextErrors).length ? null : payload;
  }

  const pending = create.isPending || update.isPending;

  const submit = handleSubmit(async (values) => {
    const payload = validatePayload();
    if (!payload) return;

    if (mode === 'edit' && object) {
      await update.mutateAsync({
        name: values.name.trim(),
        summary: values.summary?.trim() || null,
        payload,
        visibility: values.visibility,
        department_ids: values.visibility === 'department' ? values.department_ids : [],
        change_note: values.change_note?.trim() ?? '',
      });
    } else {
      await create.mutateAsync({
        object_type: values.object_type,
        name: values.name.trim(),
        summary: values.summary?.trim() || null,
        payload,
        visibility: values.visibility,
        department_ids: values.visibility === 'department' ? values.department_ids : [],
      });
    }
    onClose();
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={mode === 'edit' ? `Edit ${object?.name ?? 'object'}` : 'New knowledge object'}
      description={
        mode === 'edit'
          ? 'Saving creates a new version and keeps the previous one in history.'
          : 'Manually authored objects are approved immediately and can be cited in chat.'
      }
      size="lg"
      dismissible={!pending}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button type="submit" form="okf-form" loading={pending}>
            {mode === 'edit' ? 'Save new version' : 'Create object'}
          </Button>
        </>
      }
    >
      <form id="okf-form" noValidate onSubmit={(event) => void submit(event)} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Type" htmlFor="okf-type" required>
            <Select
              id="okf-type"
              value={objectType}
              disabled={mode === 'edit'}
              onChange={(event) => switchType(event.target.value as OkfType)}
            >
              {OKF_TYPE_ORDER.map((type) => (
                <option key={type} value={type}>
                  {OKF_TYPE_LABEL[type]}
                </option>
              ))}
            </Select>
          </FormField>

          <FormField label="Name" error={errors.name?.message} required htmlFor="okf-name">
            <Input id="okf-name" invalid={Boolean(errors.name)} placeholder="Annual leave carry-forward limit" {...register('name')} />
          </FormField>
        </div>

        <FormField
          label="Summary"
          hint="Optional. One or two sentences used in search results."
          error={errors.summary?.message}
          htmlFor="okf-summary"
        >
          <Textarea id="okf-summary" rows={2} {...register('summary')} />
        </FormField>

        <fieldset className="space-y-3 rounded-xl border border-slate-200 p-3">
          <legend className="px-1 text-sm font-semibold text-slate-700">
            {OKF_TYPE_LABEL[objectType]} attributes
          </legend>
          {fields.map((field) => (
            <PayloadField
              key={field.key}
              field={field}
              value={payloadValues[field.key] ?? ''}
              error={payloadErrors[field.key]}
              onChange={(value) => setPayloadValues((current) => ({ ...current, [field.key]: value }))}
            />
          ))}
        </fieldset>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Visibility" htmlFor="okf-visibility">
            <Select id="okf-visibility" {...register('visibility')}>
              <option value="all">{VISIBILITY_LABEL.all}</option>
              <option value="department">{VISIBILITY_LABEL.department}</option>
              <option value="admin_only">{VISIBILITY_LABEL.admin_only}</option>
            </Select>
          </FormField>

          {mode === 'edit' ? (
            <FormField label="Change note" error={errors.change_note?.message} required htmlFor="okf-note">
              <Input
                id="okf-note"
                placeholder="Why is this changing?"
                invalid={Boolean(errors.change_note)}
                {...register('change_note')}
              />
            </FormField>
          ) : null}
        </div>

        {visibility === 'department' ? (
          <fieldset>
            <legend className="mb-1.5 text-sm font-medium text-slate-700">Departments</legend>
            {departments.isPending ? (
              <p className="flex items-center gap-2 text-sm text-slate-500">
                <Spinner /> Loading departments…
              </p>
            ) : (
              <div className="grid max-h-36 gap-1 overflow-y-auto rounded-xl border border-slate-200 p-2 sm:grid-cols-2">
                {(departments.data ?? []).map((department) => {
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
                        className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                        checked={checked}
                        onChange={(event) =>
                          setValue(
                            'department_ids',
                            event.target.checked
                              ? [...selectedDepartments, department.id]
                              : selectedDepartments.filter((id) => id !== department.id),
                            { shouldValidate: true },
                          )
                        }
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
      </form>
    </Modal>
  );
}

function PayloadField({
  field,
  value,
  error,
  onChange,
}: {
  field: OkfFieldSpec;
  value: string;
  error?: string;
  onChange: (value: string) => void;
}) {
  const id = `okf-attr-${field.key}`;
  const label = field.type === 'array' ? `${field.label} (comma separated)` : field.label;

  return (
    <FormField label={label} error={error} required={field.required} htmlFor={id}>
      {field.type === 'text' ? (
        <Textarea
          id={id}
          rows={2}
          value={value}
          invalid={Boolean(error)}
          placeholder={field.placeholder}
          onChange={(event) => onChange(event.target.value)}
        />
      ) : (
        <Input
          id={id}
          value={value}
          invalid={Boolean(error)}
          placeholder={field.placeholder}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </FormField>
  );
}
