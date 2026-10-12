import type { PublicQuote } from '../api/quotes';

export interface QuoteConfirmation {
  action: 'freeze' | 'revision';
  projectId: number;
  previewToken: string;
  amount: string;
  previousAmount?: string;
}

export function captureQuoteConfirmation(
  action: QuoteConfirmation['action'],
  projectId: number,
  pendingQuote: PublicQuote | null,
  previewToken: string,
  currentQuote: PublicQuote | null,
): QuoteConfirmation | null {
  if (!pendingQuote?.export_allowed || !previewToken || (action === 'revision' && currentQuote?.status !== 'fixed')) return null;
  return { action, projectId, previewToken, amount: pendingQuote.totals.grand_total, previousAmount: action === 'revision' ? currentQuote!.totals.grand_total : undefined };
}
