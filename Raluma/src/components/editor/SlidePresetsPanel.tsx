import React from 'react';
import { Check } from 'lucide-react';

import { SlideRoomViewSVG } from './SlideDiagrams';
import {
  sectionMatches,
  SLIDE_HARDWARE_PRESETS,
  SLIDE_ONE_ROW_LAYOUTS,
  SLIDE_TWO_ROW_LAYOUTS,
  slideLayoutUpdates,
} from './slidePresets';
import type { SlideHardwarePreset, SlideLayoutPreset } from './slidePresets';
import type { Section } from './types';

function HardwareGlyph({ id }: { id: string }) {
  return (
    <svg viewBox="0 0 34 34" aria-hidden="true" className="h-8 w-8 shrink-0">
      <rect x="4" y="3" width="26" height="28" rx="5" fill="var(--theme-accent)" fillOpacity="0.06" stroke="var(--theme-accent)" strokeOpacity="0.25" />
      {id === 'knob-floor' && <circle cx="17" cy="15" r="4" fill="var(--theme-accent)" fillOpacity="0.8" />}
      {id === 'brace-lock' && (
        <>
          <line x1="14" y1="9" x2="14" y2="22" stroke="var(--theme-accent)" strokeWidth="2.5" strokeLinecap="round" />
          <rect x="19" y="18" width="6" height="5" rx="1" fill="var(--theme-accent)" fillOpacity="0.75" />
        </>
      )}
      {id === 'rs112-floor' && <rect x="14" y="6" width="6" height="20" rx="1" fill="var(--theme-accent)" fillOpacity="0.55" stroke="var(--theme-accent)" strokeOpacity="0.8" />}
      {id !== 'brace-lock' && (
        <>
          <rect x="8" y="25" width="5" height="4" rx="1" fill="var(--theme-accent)" fillOpacity="0.65" />
          <rect x="21" y="25" width="5" height="4" rx="1" fill="var(--theme-accent)" fillOpacity="0.65" />
        </>
      )}
    </svg>
  );
}

function LayoutCard({
  section,
  preset,
  active,
  hardware,
  onApply,
}: {
  section: Section;
  preset: SlideLayoutPreset;
  active: boolean;
  hardware?: SlideHardwarePreset;
  onApply: () => void;
}) {
  const preview = {
    ...section,
    ...preset.updates,
    ...(preset.updates.slideRows === 2 ? hardware?.updates : {}),
  };

  return (
    <button
      type="button"
      data-slide-layout-preset={preset.id}
      aria-pressed={active}
      onClick={onApply}
      className={`group relative min-w-0 overflow-hidden rounded-2xl border p-1.5 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 ${
        active
          ? 'border-accent/70 bg-accent/12 shadow-sm shadow-accent/10'
          : 'border-tint/25 bg-surface/35 hover:border-accent/45 hover:bg-accent/[0.07]'
      }`}
    >
      <span data-slide-preset-preview className="flex h-20 items-center justify-center rounded-lg bg-page/55 [&_svg]:h-full [&_svg]:w-full">
        <SlideRoomViewSVG section={preview} compact />
      </span>
      <span className="mt-1 flex h-5 items-center justify-between gap-1 px-0.5">
        <span className="min-w-0 truncate text-[11px] font-bold text-fg/85">{preset.title}</span>
        {active && (
          <span className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-accent text-white">
            <Check className="h-3 w-3" />
          </span>
        )}
      </span>
    </button>
  );
}

export function SlidePresetsPanel({
  section,
  onApply,
}: {
  section: Section;
  onApply: (updates: Partial<Section>) => void;
}) {
  if (section.system !== 'СЛАЙД') return null;

  const isTwoRows = section.slideRows === 2;
  const layouts = isTwoRows ? SLIDE_TWO_ROW_LAYOUTS : SLIDE_ONE_ROW_LAYOUTS;
  const activeHardware = isTwoRows
    ? SLIDE_HARDWARE_PRESETS.find(item => sectionMatches(section, item.updates))
    : undefined;
  const activeLayout = layouts.find(item => sectionMatches(section, item.match));
  const previewHardware = activeHardware ?? SLIDE_HARDWARE_PRESETS[0];

  return (
    <section data-slide-presets data-slide-presets-layout="beside-heading" className="min-w-0 rounded-2xl border border-tint/25 bg-surface/20 p-2">
      <div className={isTwoRows ? 'grid gap-2 lg:grid-cols-[minmax(0,1fr)_176px]' : ''}>
        <div className="min-w-0">
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
            {layouts.map(preset => (
              <React.Fragment key={preset.id}>
                <LayoutCard
                  section={section}
                  preset={preset}
                  hardware={previewHardware}
                  active={activeLayout?.id === preset.id}
                  onApply={() => onApply(slideLayoutUpdates(section, preset))}
                />
              </React.Fragment>
            ))}
          </div>
        </div>

        {isTwoRows && (
          <div className="lg:border-l lg:border-tint/20 lg:pl-2">
            <div data-slide-hardware-grid className="grid gap-1 sm:grid-cols-3 lg:grid-cols-1">
              {SLIDE_HARDWARE_PRESETS.map(preset => {
                const active = activeHardware?.id === preset.id;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    data-slide-hardware-preset={preset.id}
                    aria-pressed={active}
                    onClick={() => onApply(preset.updates)}
                    className={`group relative flex min-w-0 items-center gap-1 rounded-lg border px-1.5 py-1 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 ${
                      active
                        ? 'border-accent/70 bg-accent/12'
                        : 'border-tint/25 bg-surface/35 hover:border-accent/45 hover:bg-accent/[0.07]'
                    }`}
                  >
                    <HardwareGlyph id={preset.id} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[11px] font-bold text-fg/80">{preset.title}</span>
                      <span className="block truncate text-[9px] text-fg/65">{preset.description}</span>
                    </span>
                    {active && <Check className="absolute right-1 top-1 h-2.5 w-2.5 text-accent" />}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
