/** Grouped BOOK operations keep the old independent upper/lower field keys. */
export function collectProductionSheetChanges(doc: Document): Record<string, unknown> {
  const changed: Record<string, unknown> = {};
  doc.querySelectorAll<HTMLElement>('[data-field]').forEach(el => {
    const field = el.dataset.field!;
    const current = el.textContent?.trim() ?? '';
    if (current === (el.dataset.original ?? '')) return;
    changed[field] = current;
    for (const alias of (el.dataset.fieldAliases || '').split(/\s+/).filter(Boolean)) {
      changed[alias] = current;
    }
  });
  return changed;
}

export function acknowledgeProductionSheetChanges(doc: Document, saved: Record<string, unknown>): void {
  doc.querySelectorAll<HTMLElement>('[data-field]').forEach(el => {
    const field = el.dataset.field!;
    if (Object.prototype.hasOwnProperty.call(saved, field)) {
      el.dataset.original = String(saved[field]);
    }
  });
}
