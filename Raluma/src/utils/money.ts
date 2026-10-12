export function money(value: unknown): string {
  const amount = Number(value ?? 0);
  return `${(Number.isFinite(amount) ? amount : 0).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`;
}

export function numericDraft(value: unknown): number | null {
  const text = String(value ?? '').trim().replace(',', '.');
  if (!text) return null;
  const amount = Number(text);
  return Number.isFinite(amount) ? amount : null;
}

export function validMoney(value: unknown, maximum?: number): boolean {
  const amount = numericDraft(value);
  return amount !== null && amount >= 0 && (maximum === undefined || amount <= maximum);
}

export function profilePricingMetres(length: unknown, pieces: unknown): number | null {
  const mm = numericDraft(String(length ?? '').replace(/\s*(?:мм|mm)\s*$/i, ''));
  const count = numericDraft(pieces);
  return mm !== null && mm > 0 && count !== null && count > 0 ? mm * count / 1000 : null;
}

export const categoryNames = { construction: 'Изделия', profile: 'Профили отдельно', component: 'Аксессуары', service: 'Услуги' } as const;
