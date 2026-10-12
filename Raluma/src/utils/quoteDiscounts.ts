import type { QuoteDiscountRule } from '../api/quotes';

// Match the server's stages without losing additional rules or changing their
// order within a stage. Never mutate the currently displayed/saved config.
export function orderQuoteDiscounts(rules: readonly QuoteDiscountRule[]): QuoteDiscountRule[] {
  const stage = (rule: QuoteDiscountRule) => rule.scope !== 'order' ? 0 : rule.mode === 'percent' ? 1 : 2;
  return [...rules].sort((left, right) => stage(left) - stage(right));
}
