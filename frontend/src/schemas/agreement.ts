import { z } from "zod";

import { todayIsoDay } from "@/utils/format";

/**
 * A money amount typed by a person. Kept as text, never a float. "49,95" (Dutch comma)
 * is accepted and converted to "49.95" before sending (see toAmountString).
 */
const amountField = z
  .string()
  .trim()
  .regex(/^\d{1,10}([.,]\d{1,2})?$/, "Enter an amount like 49.95, with at most 2 decimals.")
  .refine((value) => Number(value.replace(",", ".")) > 0, "The amount must be more than 0.");

/**
 * Agreement form rules, mirroring the API so mistakes show while typing. The server
 * checks everything again; its "today" (in the billing time zone) is the one that counts.
 */
export const agreementCreateSchema = z.object({
  customer_id: z.string().min(1, "Choose a customer."),
  description: z
    .string()
    .trim()
    .min(1, "Description is required.")
    .max(255, "Description can be at most 255 characters."),
  amount: amountField,
  anchor_date: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, "Choose the first billing date.")
    // ISO dates compare correctly as text: "2027-01-31" >= "2027-01-15".
    .refine((value) => value >= todayIsoDay(), "The first billing date cannot be in the past."),
  total_cycles: z
    .number({ error: "Enter the number of months." })
    .int("Use a whole number of months.")
    .min(1, "At least 1 month.")
    .max(120, "At most 120 months."),
});

export type AgreementCreateValues = z.infer<typeof agreementCreateSchema>;

export const agreementEditSchema = agreementCreateSchema.pick({ description: true });
export type AgreementEditValues = z.infer<typeof agreementEditSchema>;

/** "49,95" -> "49.95" (the API's decimal format). */
export function toAmountString(value: string): string {
  return value.trim().replace(",", ".");
}

export const changeAmountSchema = z.object({
  from_cycle: z.number({ error: "Choose the first month." }).int().min(1, "Choose the first month."),
  amount: amountField,
});
export type ChangeAmountValues = z.infer<typeof changeAmountSchema>;
