import { z } from 'zod'

export const MIN_PASSWORD_LENGTH = 12
export const MAX_PASSWORD_LENGTH = 128
export const MAX_NAME_LENGTH = 100
export const MAX_EMAIL_LENGTH = 254

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

export const logInSchema = z.object({
  email: z.string().trim().min(1, 'Enter your email address.'),
  password: z.string().min(1, 'Enter your password.'),
})

export type LogInValues = z.infer<typeof logInSchema>

export const newAccountSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Enter your name.')
    .max(MAX_NAME_LENGTH, `The name must be at most ${MAX_NAME_LENGTH} characters.`),
  email: z
    .string()
    .trim()
    .min(1, 'Enter your email address.')
    .max(MAX_EMAIL_LENGTH, `The email address must be at most ${MAX_EMAIL_LENGTH} characters.`)
    .regex(EMAIL, 'Enter an email address like name@example.com.'),
  password: z
    .string()
    .min(MIN_PASSWORD_LENGTH, `Use at least ${MIN_PASSWORD_LENGTH} characters.`)
    .max(MAX_PASSWORD_LENGTH, `Use at most ${MAX_PASSWORD_LENGTH} characters.`),
})

export type NewAccountValues = z.infer<typeof newAccountSchema>

export const NEW_ACCOUNT_FIELDS = ['name', 'email', 'password'] as const
