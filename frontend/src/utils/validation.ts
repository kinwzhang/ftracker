import { z } from 'zod';

export const taskSchema = z.object({
  task_name: z.string().min(1, 'Task name is required'),
  assigned_to: z.string().min(1, 'Assigned to is required'),
  sla_days: z.number().int().min(1, 'SLA days must be at least 1'),
  sla_type: z.enum(['Working Day', 'Calendar Day']),
  group: z.number().nullable(),
});

export const templateSchema = z.object({
  task_name: z.string().min(1, 'Task name is required'),
  assigned_to: z.string().min(1, 'Assigned to is required'),
  sla_days: z.number().int().min(1, 'SLA days must be at least 1'),
  sla_type: z.enum(['Working Day', 'Calendar Day']),
  sort_order: z.number().int().min(0, 'Sort order must be non-negative'),
  group: z.number().nullable(),
});

export const groupSchema = z.object({
  name: z.string().min(1, 'Group name is required'),
  sort_order: z.number().int().min(0, 'Sort order must be non-negative'),
});

export type TaskFormData = z.infer<typeof taskSchema>;
export type TemplateFormData = z.infer<typeof templateSchema>;
export type GroupFormData = z.infer<typeof groupSchema>;
