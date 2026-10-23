export const WAITLIST_AUDIENCES = ["Individual", "Team / company"] as const;

export type WaitlistAudience = (typeof WAITLIST_AUDIENCES)[number];

export const WAITLIST_ROLES = [
  "Individual",
  "Founder",
  "Ops",
  "Engineering",
  "Product",
  "Freelancer",
  "Student",
  "Other",
] as const;

export type WaitlistRole = (typeof WAITLIST_ROLES)[number];

export const WAITLIST_HEARD_FROM = [
  "Friend or colleague",
  "LinkedIn",
  "X / Twitter",
  "Search",
  "Event or meetup",
  "Other",
] as const;

export type WaitlistHeardFrom = (typeof WAITLIST_HEARD_FROM)[number];

export const MAX_WAITLIST_USE_CASE = 280;

export function isWaitlistAudience(value: string): value is WaitlistAudience {
  return (WAITLIST_AUDIENCES as readonly string[]).includes(value);
}

export function isWaitlistRole(value: string): value is WaitlistRole {
  return (WAITLIST_ROLES as readonly string[]).includes(value);
}

export function isWaitlistHeardFrom(value: string): value is WaitlistHeardFrom {
  return (WAITLIST_HEARD_FROM as readonly string[]).includes(value);
}
