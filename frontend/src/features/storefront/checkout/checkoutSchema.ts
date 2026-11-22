import { z } from 'zod'

import type { CheckoutBody, Payment, RequestedLine } from '../../../api/orders'

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/
const EXPIRY_PATTERN = /^(0[1-9]|1[0-2])\/(\d{2})$/
const CVC_PATTERN = /^\d{3,4}$/

export const CHECKOUT_FIELDS = [
  'customer.name',
  'customer.email',
  'payment.card_number',
  'payment.expiry',
  'payment.cvc',
] as const

export const SERVER_FIELD_ALIASES: Record<string, string> = {
  'payment.expiry_month': 'payment.expiry',
  'payment.expiry_year': 'payment.expiry',
}

export type CheckoutValues = {
  customer: { name: string; email: string }
  payment: { card_number: string; expiry: string; cvc: string }
}

export const emptyCheckout: CheckoutValues = {
  customer: { name: '', email: '' },
  payment: { card_number: '', expiry: '', cvc: '' },
}

export function cardDigits(number: string): string {
  return number.replace(/[\s-]/g, '')
}

export function luhnValid(digits: string): boolean {
  let total = 0
  for (let index = 0; index < digits.length; index += 1) {
    let value = Number(digits[digits.length - 1 - index])
    if (index % 2 === 1) {
      value *= 2
      if (value > 9) {
        value -= 9
      }
    }
    total += value
  }
  return total % 10 === 0
}

export function validCardNumber(number: string): boolean {
  const digits = cardDigits(number)
  return /^\d{12,19}$/.test(digits) && luhnValid(digits)
}

export function parseExpiry(expiry: string): { month: number; year: number } | null {
  const match = EXPIRY_PATTERN.exec(expiry.trim())
  if (match === null) {
    return null
  }
  return { month: Number(match[1]), year: 2000 + Number(match[2]) }
}

export function isExpired(month: number, year: number, today: Date): boolean {
  const currentYear = today.getFullYear()
  const currentMonth = today.getMonth() + 1
  return year < currentYear || (year === currentYear && month < currentMonth)
}

const customer = z.object({
  name: z
    .string()
    .trim()
    .min(1, { message: 'Enter your name.' })
    .max(200, { message: 'Use at most 200 characters.' }),
  email: z
    .string()
    .trim()
    .regex(EMAIL_PATTERN, { message: 'Enter an email address like name@example.com.' }),
})

const payment = z
  .object({
    card_number: z.string().refine(validCardNumber, { message: 'This card number is not valid.' }),
    expiry: z.string(),
    cvc: z
      .string()
      .trim()
      .regex(CVC_PATTERN, { message: 'The security code is the 3 or 4 digits on the card.' }),
  })
  .superRefine((values, context) => {
    const expiry = parseExpiry(values.expiry)
    if (expiry === null) {
      context.addIssue({ code: 'custom', path: ['expiry'], message: 'Use the format MM/YY.' })
    } else if (isExpired(expiry.month, expiry.year, new Date())) {
      context.addIssue({ code: 'custom', path: ['expiry'], message: 'This card has expired.' })
    }
  })

export const paidCheckoutSchema = z.object({ customer, payment })

export const freeCheckoutSchema = z.object({
  customer,
  payment: z.object({ card_number: z.string(), expiry: z.string(), cvc: z.string() }),
})

export function paymentOf(values: CheckoutValues['payment']): Payment {
  const expiry = parseExpiry(values.expiry) ?? { month: 0, year: 0 }
  return {
    card_number: values.card_number.trim(),
    expiry_month: expiry.month,
    expiry_year: expiry.year,
    cvc: values.cvc.trim(),
  }
}

export function checkoutBody(
  values: CheckoutValues,
  lines: RequestedLine[],
  paymentRequired: boolean,
): CheckoutBody {
  const body: CheckoutBody = {
    customer: { name: values.customer.name.trim(), email: values.customer.email.trim() },
    lines,
  }
  return paymentRequired ? { ...body, payment: paymentOf(values.payment) } : body
}
