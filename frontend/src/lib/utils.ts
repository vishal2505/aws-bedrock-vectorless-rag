import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function slugify(name: string): string {
  return name
    .replace(/\.[^.]+$/, '')          // remove extension
    .replace(/[^a-zA-Z0-9-]/g, '-')   // replace non-alphanumeric
    .replace(/-+/g, '-')               // collapse dashes
    .toLowerCase()
    .slice(0, 60)
}
