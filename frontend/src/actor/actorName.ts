import { z } from 'zod'

export const MAX_ACTOR_LENGTH = 100

const CONTROL_CHARACTERS = /\p{Cc}/u

export const actorNameSchema = z
  .string()
  .refine((value) => !CONTROL_CHARACTERS.test(value), {
    message: 'The name must not contain line breaks, tabs or other control characters.',
  })
  .transform((value) => value.trim())
  .pipe(
    z
      .string()
      .min(1, { message: 'Tell us who is making this change.' })
      .max(MAX_ACTOR_LENGTH, {
        message: `The name must be at most ${MAX_ACTOR_LENGTH} characters.`,
      }),
  )

export const actorFormSchema = z.object({ name: actorNameSchema })
