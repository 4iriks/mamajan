import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { SlideCalcPreview } from '../../src/api/projects';
import { RemoteCountInput } from '../../src/components/editor/LiftForm';
import { SlideRoomViewSVG, SlideSchemeSVG } from '../../src/components/editor/SlideDiagrams';
import type { Section } from '../../src/components/editor/types';
import '../../src/index.css';

const slideSection: Section = {
  id: 'theme-check',
  name: 'Секция 1',
  system: 'СЛАЙД',
  width: 3200,
  height: 2400,
  panels: 4,
  quantity: 1,
  glassType: '10ММ ПРОЗРАЧНОЕ',
  paintingType: 'RAL стандарт',
  cornerLeft: false,
  cornerRight: false,
  rails: 3,
  threshold: 'Стандартный анод',
  firstPanelInside: 'Справа',
  interGlassProfile: 'Алюминиевый RS2061',
  floorLatchesLeft: false,
  floorLatchesRight: false,
  profileLeftWall: false,
  profileLeftLockBar: false,
  profileLeftPBar: false,
  profileLeftHandleBar: false,
  profileLeftBubble: false,
  profileRightWall: false,
  profileRightLockBar: false,
  profileRightPBar: false,
  profileRightHandleBar: false,
  profileRightBubble: false,
  handleLeft: 'Ручка-кноб RS3014',
  handleRight: 'Ручка-кноб RS3014',
  lockLeft: 'Без',
  lockRight: 'Без',
};

const slideCalc: SlideCalcPreview = {
  glass: [
    { position: 'Крайние', width_mm: 810, height_mm: 2294, qty: 2, glass_profile_length: 810 },
    { position: 'Промежуточные', width_mm: 794, height_mm: 2294, qty: 2, glass_profile_length: 791 },
  ],
  profiles: [],
  panel_rails: [0, 1, 2, 0],
};

const glassTypes = [
  '10ММ ПРОЗРАЧНОЕ',
  '10ММ БРОНЗА В МАССЕ',
  '10ММ СЕРОЕ В МАССЕ',
  '10ММ МАТОВОЕ',
  '10ММ ПРОСВЕТЛЕННОЕ',
  'ТРИПЛЕКС 4.1.4',
];

function Harness() {
  const [sharedCount, setSharedCount] = useState(3);

  return (
    <main style={{ minHeight: '100vh', padding: 24, background: 'var(--theme-bg)', color: 'var(--theme-fg)' }}>
      <section style={{ position: 'fixed', left: -10000, top: 0 }}>
        <RemoteCountInput channel={1} value={sharedCount} onChange={setSharedCount} />
        <RemoteCountInput channel={6} value={sharedCount} onChange={setSharedCount} />
        <output data-shared-count>{sharedCount}</output>
        <output data-button-section-count>9</output>
        <button type="button" data-external-update onClick={() => setSharedCount(7)}>
          External update
        </button>
      </section>
      <section
        data-slide-theme-check
        style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 16 }}
      >
        {glassTypes.map(glassType => {
          const section = { ...slideSection, glassType };
          return (
            <article key={glassType} style={{ padding: 12, border: '1px solid var(--theme-border)' }}>
              <strong>{glassType}</strong>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <SlideRoomViewSVG section={section} calc={slideCalc} />
                <SlideSchemeSVG section={section} calc={slideCalc} />
              </div>
            </article>
          );
        })}
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<Harness />);
