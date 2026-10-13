import { useState } from 'react';
import { activeCsConfig } from './csPresets';
import { csChangeDimensionMode } from './csGeometry';
import type { CsConfig, Section } from './types';

export function CsDimensionModeField({ section, update }: {
  section: Section;
  update: (changes: Partial<Section>) => void;
}) {
  const [error, setError] = useState('');
  const mode = section.csConfig?.dimensionMode ?? 'installation';
  const changeMode = (next: CsConfig['dimensionMode']) => {
    if (!next || next === mode) return;
    try {
      const changes = csChangeDimensionMode(activeCsConfig(section), next);
      setError('');
      update(changes);
    } catch (failure) {
      setError(`Тип размеров не изменён: ${(failure as Error).message}`);
    }
  };
  return <div className="mb-3 space-y-1.5" data-cs-dimension-mode>
    <div role="group" aria-label="Тип размеров ЦС" className="grid grid-cols-2 gap-2">
      {([['installation', 'Наружные размеры'], ['clear', 'Световой проём']] as const).map(([value, label]) => (
        <button key={value} type="button" aria-pressed={mode === value} onClick={() => changeMode(value)}
          className={`rounded-lg border px-2 py-2 text-xs font-bold ${mode === value
            ? 'border-accent/50 bg-accent/10 text-accent' : 'border-tint/25 text-fg/65 hover:border-accent/50'}`}>
          {label}
        </button>
      ))}
    </div>
    <p className="text-xs text-fg/65">При переключении размеры пересчитываются, сама конструкция не меняется.</p>
    {error && <p role="alert" className="text-xs text-red-500">{error}</p>}
  </div>;
}
