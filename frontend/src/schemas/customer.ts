import { z } from "zod";

/**
 * Customer form rules, mirroring the Django model so mistakes show while typing.
 * Django checks everything again (the browser can be bypassed), and any server-side
 * error is mapped back onto the matching field by CustomerForm.
 */
const required = (label: string, max: number) =>
  z
    .string()
    .trim()
    .min(1, `${label} is required.`)
    .max(max, `${label} can be at most ${max} characters.`);

const optional = (label: string, max: number) =>
  z.string().trim().max(max, `${label} can be at most ${max} characters.`);

export const customerFormSchema = z.object({
  external_customer_id: required("External customer id", 64).regex(
    /^[A-Za-z0-9][A-Za-z0-9._-]*$/,
    "Use letters, digits, '.', '_' or '-', starting with a letter or digit.",
  ),
  customer_type: z.enum(["PERSON", "COMPANY"]),
  name: required("Name", 255),
  email: z.string().trim().pipe(z.email("Enter a valid email address.")),
  phone: optional("Phone", 32),
  address_line1: required("Address", 255),
  address_line2: optional("Address line 2", 255),
  postal_code: required("Postal code", 20),
  city: required("City", 100),
  // Any case is fine: the server upper-cases it ("nl" -> "NL").
  country_code: z
    .string()
    .trim()
    .regex(/^[A-Za-z]{2}$/, "Use a two-letter country code, e.g. NL."),
});

export type CustomerFormValues = z.infer<typeof customerFormSchema>;

export const EMPTY_CUSTOMER_FORM: CustomerFormValues = {
  external_customer_id: "",
  customer_type: "PERSON",
  name: "",
  email: "",
  phone: "",
  address_line1: "",
  address_line2: "",
  postal_code: "",
  city: "",
  country_code: "",
};
