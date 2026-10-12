import { useEffect, useRef } from 'react';
import type { QuoteConfirmation } from '../utils/quoteConfirmation';
import { money } from '../utils/money';

export function QuoteConfirmationDialog({ confirmation, busy, onConfirm, onCancel }: {
  confirmation: QuoteConfirmation;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const previousFocus = document.activeElement;
    cancelRef.current?.focus();
    return () => { if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus(); };
  }, []);
  useEffect(() => { if (busy) panelRef.current?.focus(); }, [busy]);
  const isRevision = confirmation.action === 'revision';
  return <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/50 p-4">
    <section ref={panelRef} tabIndex={-1} role="alertdialog" aria-modal="true" aria-labelledby="quote-confirm-title" aria-describedby="quote-confirm-description" className="w-full max-w-md rounded-2xl border border-tint/30 bg-modal p-5 text-fg shadow-2xl" onKeyDown={event => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); if (!busy) onCancel(); }
      if (event.key === 'Tab') {
        if (busy) { event.preventDefault(); return; }
        if (event.shiftKey && document.activeElement === cancelRef.current) { event.preventDefault(); confirmRef.current?.focus(); }
        if (!event.shiftKey && document.activeElement === confirmRef.current) { event.preventDefault(); cancelRef.current?.focus(); }
      }
    }}>
      <h3 id="quote-confirm-title" className="text-lg font-bold">{isRevision ? 'Подтвердить новую редакцию КП' : 'Подтвердить фиксацию КП'}</h3>
      <div className="my-4 space-y-2 rounded-xl border border-accent/25 bg-accent/5 p-3">
        {isRevision && <p className="text-sm text-fg/70">Сейчас зафиксировано: <b>{money(confirmation.previousAmount)}</b></p>}
        <p className="text-sm">{isRevision ? 'Новая сумма КП:' : 'Сумма КП:'} <b className="text-lg">{money(confirmation.amount)}</b></p>
      </div>
      <p id="quote-confirm-description" className="text-sm text-fg/75">{isRevision ? 'Предыдущая редакция останется в истории. Будет зафиксирована новая редакция с указанной суммой.' : 'После фиксации дальнейшие изменения оформляются новой редакцией. Само скачивание документа не фиксирует цены.'} Если расчёт успел измениться, потребуется проверить новую сумму и подтвердить её ещё раз.</p>
      <div className="mt-5 flex justify-end gap-2">
        <button ref={cancelRef} type="button" disabled={busy} onClick={onCancel} className="rounded-lg border border-tint/30 px-4 py-2 text-sm font-semibold disabled:opacity-40">Отмена</button>
        <button ref={confirmRef} type="button" disabled={busy} onClick={onConfirm} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">{busy ? 'Фиксируем…' : 'Подтвердить и зафиксировать'}</button>
      </div>
    </section>
  </div>;
}
