import { Section } from './types';

// ── Checkbox ──────────────────────────────────────────────────────────────────

export function Checkbox({ checked, onChange, label }: { checked: boolean; onChange: () => void; label: string }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer" onClick={onChange}>
      <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all flex-shrink-0 ${checked ? 'bg-[#4fd1c5] border-[#4fd1c5]' : 'border-[#2a7a8a]/40 bg-black/20'}`}>
        {checked && <div className="w-2.5 h-2.5 bg-[#0c1d2d] rounded-sm" />}
      </div>
      <span className="text-xs font-medium text-white/60">{label}</span>
    </label>
  );
}

// ── ToggleGroup ───────────────────────────────────────────────────────────────

export function ToggleGroup({ value, options, onChange }: { value?: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div className="flex gap-2 flex-wrap">
      {options.map(opt => (
        <button key={opt} onClick={() => onChange(opt)}
          className={`flex-1 py-1.5 rounded-xl border font-bold text-xs transition-all min-w-0 ${
            value === opt ? 'bg-[#4fd1c5]/10 border-[#4fd1c5]/50 text-[#4fd1c5]' : 'bg-black/10 border-[#2a7a8a]/20 text-white/40 hover:border-[#2a7a8a]/50'
          }`}
        >{opt}</button>
      ))}
    </div>
  );
}

// ── RadioList ─────────────────────────────────────────────────────────────────

export function RadioList({ value, options, onChange, noneLabel }: { value?: string; options: string[]; onChange: (v: string | undefined) => void; noneLabel?: string }) {
  const allOptions = noneLabel ? [noneLabel, ...options] : options;
  return (
    <div className="space-y-1.5">
      {allOptions.map(opt => {
        const isNone = opt === noneLabel;
        const active = isNone ? !value : value === opt;
        return (
          <button key={opt} onClick={() => onChange(isNone ? undefined : opt)}
            className={`w-full text-left px-3 py-1.5 rounded-xl border transition-all text-xs ${
              active ? 'bg-[#4fd1c5]/10 border-[#4fd1c5]/50 text-[#4fd1c5]' : 'border-[#2a7a8a]/20 bg-black/10 text-white/40 hover:border-[#4fd1c5]/30'
            }`}
          >{opt}</button>
        );
      })}
    </div>
  );
}

// ── SectionDivider ────────────────────────────────────────────────────────────

export function SectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 pt-1">
      <span className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40 whitespace-nowrap">{label}</span>
      <div className="flex-1 h-px bg-[#2a7a8a]/20" />
    </div>
  );
}

// ── ProfileCheckbox ───────────────────────────────────────────────────────────

export function ProfileCheckbox({ checked, onChange, label, indent, disabled }: { checked: boolean; onChange: () => void; label: string; indent?: boolean; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={disabled ? undefined : onChange}
      disabled={disabled}
      className={`w-full text-left flex items-center gap-2 px-2.5 py-1.5 rounded-lg transition-all text-xs my-0.5 ${
        indent ? 'ml-4 w-[calc(100%-1rem)]' : ''
      } ${
        disabled
          ? 'opacity-25 cursor-not-allowed border border-transparent text-white/30'
          : checked
            ? 'bg-[#4fd1c5]/10 border border-[#4fd1c5]/40 text-[#4fd1c5]'
            : 'border border-[#2a7a8a]/20 bg-black/5 text-white/50 hover:border-[#2a7a8a]/40 hover:text-white/70'
      }`}
    >
      <div className={`w-3.5 h-3.5 rounded-sm border-2 flex-shrink-0 flex items-center justify-center transition-all ${
        checked ? 'bg-[#4fd1c5] border-[#4fd1c5]' : 'border-[#2a7a8a]/40 bg-transparent'
      }`}>
        {checked && <div className="w-1.5 h-1.5 bg-[#0c1d2d] rounded-sm" />}
      </div>
      <span className="leading-tight">{label}</span>
    </button>
  );
}

// ── Section card helpers ──────────────────────────────────────────────────────

export function getSectionTypeLabel(s: Section): string {
  switch (s.system) {
    case 'СЛАЙД': {
      const rows = s.rails === 5 ? '2 ряда от центра' : '1 ряд';
      return `${rows} · ${s.panels ?? 3} пан.`;
    }
    case 'КНИЖКА': {
      const sub = s.bookSubtype === 'angle' ? 'с углом' : s.bookSubtype === 'doors_and_angle' ? 'с дв. и углом' : 'с дверями';
      return `${sub} · ${s.panels ?? 3} пан.`;
    }
    case 'ЛИФТ':
      return `${s.panels ?? 2} пан.`;
    case 'ЦС':
      return s.csShape || '';
    case 'КОМПЛЕКТАЦИЯ':
      return s.doorSystem || '';
    default:
      return '';
  }
}

export function getSectionColorLabel(s: Section): string {
  if (s.paintingType === 'Анодированный') return 'Анод.';
  if (s.paintingType.includes('RAL')) return s.ralColor ? `RAL ${s.ralColor}` : 'RAL';
  return '';
}
