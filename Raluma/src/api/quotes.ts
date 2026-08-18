import client from './client';

export interface QuotePanelGeometry {
  index: number;
  number: number;
  width_mm: string;
  rail: number;
  direction: string;
  deaf: boolean;
}

export interface QuoteSectionDetails {
  section_id: number;
  name: string;
  width_mm: string;
  height_mm: string;
  panels: number;
  quantity: number;
  glass_area_m2: string;
  glass_supplied?: boolean;
  glass_weight_kg?: string;
  color: string;
  system: string;
  glass_type: string;
  threshold: string;
  rails: number;
  slide_rows: number;
  first_panel_inside: string;
  unused_track: string;
  slide_direction: string;
  panel_width_total_mm: string;
  panel_geometry: QuotePanelGeometry[];
}

export interface QuoteBreakdownLine {
  sku: string;
  name: string;
  quantity: string;
  unit: string;
  unit_price: number;
  line_total: number;
}

export interface QuoteLine {
  id: string;
  name: string;
  category: 'profile' | 'construction' | 'component' | 'service';
  quantity: string;
  unit: string;
  unit_price_before_discount: string;
  discount_percent: string;
  unit_discount_amount: string;
  unit_final_price: string;
  line_total_before_discount: string;
  line_discount_amount: string;
  line_total: string;
  document_line_total_before_discount: number;
  document_line_discount_amount: number;
  document_line_total: number;
  document_unit_price_before_discount: number;
  document_unit_discount_amount: number;
  document_unit_final_price: number;
  section_details?: QuoteSectionDetails;
  breakdown?: QuoteBreakdownLine[];
  component_details?: {
    catalog_item_id?: number;
    finish_variant_id?: number;
    sku: string;
    name: string;
    size: string;
    finish: string;
    unit: string;
    stage: string;
  };
}

export interface PublicQuote {
  project: { id: number; number: string; invoice_number?: string | null; order_number?: string | null; customer: string };
  revision: number;
  status: 'draft' | 'fixed';
  fixed_at: string | null;
  currency: 'RUB';
  lines: QuoteLine[];
  totals: {
    before_discount: string;
    discount: string;
    subtotal: string;
    grand_total: string;
    document_before_discount: number;
    document_discount: number;
    document_grand_total: number;
  };
  validity_days: number;
  valid_until: string;
  manufacturing_term: string;
  payment_terms: string;
  discounts: QuoteDiscountRule[];
  missing_price_count: number;
  warnings: string[];
  export_allowed: boolean;
  stale: boolean;
}

export interface QuoteManualService {
  id: string;
  name: string;
  quantity: string;
  unit: string;
  base_cost: string;
}

export interface QuotePriceOverride {
  sku: string;
  cost: string;
  comment: string;
}

export interface QuoteDiscountRule {
  id: string;
  name: string;
  scope: 'order' | 'profile' | 'construction' | 'component' | 'service';
  mode: 'percent' | 'fixed';
  value: string;
}

export interface QuoteConfig {
  validity_days: number;
  manufacturing_term: string;
  payment_terms: string;
  services: QuoteManualService[];
  discounts: QuoteDiscountRule[];
  overrides: QuotePriceOverride[];
  margin_override_comment: string;
}

export interface MarginApprovalState {
  required: boolean;
  valid: boolean;
  context_signature: string;
  target_revision: number;
  approved_revision: number | null;
  comment: string;
  approved_by: number | null;
  approved_at: string | null;
}

export interface InternalQuoteState {
  revision: number;
  status: 'draft' | 'fixed';
  stale: boolean;
  config: QuoteConfig;
  missing_prices: Array<{ sku: string; name: string; unit: string; reason: string }>;
  pending_warnings: string[];
  margin_approval: MarginApprovalState;
  calculation: Record<string, unknown>;
}

export const getPublicQuote = (projectId: number) =>
  client.get<PublicQuote>(`/api/projects/${projectId}/quote`).then(response => response.data);

export const getInternalQuote = (projectId: number) =>
  client.get<InternalQuoteState>(`/api/pricing/projects/${projectId}`).then(response => response.data);

export const updateQuoteConfig = (
  projectId: number,
  config: Omit<QuoteConfig, 'overrides' | 'margin_override_comment'>,
) => client.put<PublicQuote>(`/api/projects/${projectId}/quote/config`, config)
  .then(response => response.data);

export const updateQuoteOverrides = (
  projectId: number,
  overrides: QuotePriceOverride[],
  marginOverrideComment?: string,
) => client.put<PublicQuote>(`/api/projects/${projectId}/quote/overrides`, {
  overrides,
  ...(marginOverrideComment !== undefined
    ? { margin_override_comment: marginOverrideComment }
    : {}),
}).then(response => response.data);

export const refreshQuote = (projectId: number) =>
  client.post<PublicQuote>(`/api/projects/${projectId}/quote/refresh`)
    .then(response => response.data);
