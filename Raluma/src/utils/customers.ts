import type { ProjectList } from '../api/projects';

const BASE_CUSTOMERS = [
  'ООО ПРОЗРАЧНЫЕ РЕШЕНИЯ',
  'ООО КРОКНА ИНЖИНИРИНГ',
];

const CUSTOMER_ALIASES: Record<string, string> = {
  'ооо пр': 'ООО ПРОЗРАЧНЫЕ РЕШЕНИЯ',
  'ооо ки': 'ООО КРОКНА ИНЖИНИРИНГ',
};

const RETIRED_CUSTOMERS = new Set([
  'ооо спк',
  'ооо студия спк',
  'студия спк',
]);

function normalizeCustomer(value?: string | null) {
  const clean = (value ?? '').trim();
  if (!clean) return '';
  return CUSTOMER_ALIASES[clean.toLowerCase()] || clean;
}

export function buildCustomerOptions(
  projects: Pick<ProjectList, 'customer'>[] = [],
  userCustomer?: string | null,
  currentCustomer?: string | null,
) {
  const seen = new Map<string, string>();

  const add = (value?: string | null) => {
    const clean = normalizeCustomer(value);
    if (!clean) return;
    const key = clean.toLowerCase();
    if (RETIRED_CUSTOMERS.has(key)) return;
    if (!seen.has(key)) seen.set(key, clean);
  };

  BASE_CUSTOMERS.forEach(add);
  add(userCustomer);
  add(currentCustomer);
  projects.forEach(project => add(project.customer));

  return [...seen.values()];
}

export function filterCustomerOptions(options: string[], query: string) {
  const needle = query.trim().toLowerCase();
  if (!needle) return options;
  return options.filter(option => option.toLowerCase().includes(needle));
}
