import type { ProjectList } from '../api/projects';

const BASE_CUSTOMERS = ['ООО ПР', 'ООО КИ', 'ООО СПК'];

export function buildCustomerOptions(
  projects: Pick<ProjectList, 'customer'>[] = [],
  userCustomer?: string | null,
  currentCustomer?: string | null,
) {
  const seen = new Map<string, string>();

  const add = (value?: string | null) => {
    const clean = (value ?? '').trim();
    if (!clean) return;
    const key = clean.toLowerCase();
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
