/**
 * Small composable checks for data from outside the page: an API reply or a bundled JSON file.
 * Each check is a type guard, and `shape` takes one check per field of an interface, so the
 * compiler holds the checks to the type: a field added to the interface without a check does
 * not build.
 */

export type Guard<T> = (value: unknown) => value is T;

export const isNumber: Guard<number> = (value): value is number =>
  typeof value === "number" && Number.isFinite(value);

export const isString: Guard<string> = (value): value is string => typeof value === "string";

export const isBoolean: Guard<boolean> = (value): value is boolean => typeof value === "boolean";

/** A string the browser can read as a date and time. */
export const isTime: Guard<string> = (value): value is string =>
  typeof value === "string" && !Number.isNaN(Date.parse(value));

export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function nullable<T>(guard: Guard<T>): Guard<T | null> {
  return (value): value is T | null => value === null || guard(value);
}

export function oneOf<const T extends readonly unknown[]>(values: T): Guard<T[number]> {
  return (value): value is T[number] => values.includes(value);
}

export function listOf<T>(guard: Guard<T>): Guard<T[]> {
  return (value): value is T[] => Array.isArray(value) && value.every(guard);
}

/** An object whose keys can be anything (a tool or a domain name) and whose values pass. */
export function recordOf<T>(guard: Guard<T>): Guard<Record<string, T>> {
  return (value): value is Record<string, T> =>
    isPlainObject(value) && Object.values(value).every(guard);
}

/** An object with every one of `keys`, each value passing `guard`, and no other key. */
export function keyedBy<K extends string, T>(
  keys: readonly K[],
  guard: Guard<T>,
): Guard<Record<K, T>> {
  return (value): value is Record<K, T> =>
    isPlainObject(value) &&
    Object.keys(value).every((key) => (keys as readonly string[]).includes(key)) &&
    keys.every((key) => guard(value[key]));
}

/** An object with some of `keys` (and no other), each value passing `guard`. */
export function someKeyedBy<K extends string, T>(
  keys: readonly K[],
  guard: Guard<T>,
): Guard<Partial<Record<K, T>>> {
  return (value): value is Partial<Record<K, T>> =>
    isPlainObject(value) &&
    Object.entries(value).every(
      ([key, entry]) => (keys as readonly string[]).includes(key) && guard(entry),
    );
}

/** An object with every field of `T`, each passing its own check. Extra fields are allowed, so
 * a newer server can add one without breaking an older page. */
export function shape<T extends object>(fields: { [K in keyof T]-?: Guard<T[K]> }): Guard<T> {
  const checks = Object.entries(fields) as [string, Guard<unknown>][];
  return (value): value is T =>
    isPlainObject(value) && checks.every(([key, guard]) => guard(value[key]));
}
