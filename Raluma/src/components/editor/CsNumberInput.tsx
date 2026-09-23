import { useState } from 'react';
import { INP, LBL } from './types';

/** Keep a literal draft so zero, separators and partially typed numbers can be erased. */
export function CsNumberInput({ label, value, min = 0, max, integer = false, live = false, readOnly = false, onChange }: {
  label: string; value: number; min?: number; max?: number; integer?: boolean;
  live?: boolean; readOnly?: boolean; onChange: (value: number) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const valid = (text: string) => text.trim() !== '' && Number.isFinite(Number(text))
    && Number(text) >= min && (max === undefined || Number(text) <= max)
    && (!integer || Number.isInteger(Number(text)));
  const commit = () => {
    if (draft !== null && valid(draft)) onChange(Number(draft));
    setDraft(null);
  };
  return <label>
    <span className={LBL}>{label}</span>
    <input type="number" min={min} max={max} step={integer ? 1 : 'any'} readOnly={readOnly}
      value={draft ?? Math.round(value * 1000) / 1000} className={INP}
      aria-invalid={draft !== null && draft !== '' && !valid(draft)}
      onChange={event => {
        setDraft(event.target.value);
        if (live && valid(event.target.value)) onChange(Number(event.target.value));
      }} onBlur={commit} onKeyDown={event => {
        if (event.key === 'Enter') { event.preventDefault(); event.currentTarget.blur(); }
        if (event.key === 'Escape') { event.preventDefault(); setDraft(null); }
      }} />
  </label>;
}
