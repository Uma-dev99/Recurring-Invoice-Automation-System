import { z } from "zod";

/**
 * Client-side validation gives instant feedback only. Django validates the same
 * input again: the server is the authority, and the browser can be bypassed.
 */
export const loginSchema = z.object({
  email: z.email("Enter a valid email address."),
  password: z.string().min(1, "Password is required."),
});

export type LoginInput = z.infer<typeof loginSchema>;
