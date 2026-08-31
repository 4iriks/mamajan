import { AlertTriangle } from 'lucide-react';
import type { ReactNode } from 'react';

import { bookExtraDoorPanelOptions } from '../../constants/book';
import { Checkbox } from './FormInputs';
import { INP, LBL, SEL, Section } from './types';


const OPENINGS = [
  { value: 'inside_in', label: 'Изнутри внутрь' },
  { value: 'inside_out', label: 'Изнутри наружу' },
  { value: 'outside_out', label: 'Снаружи наружу' },
  { value: 'outside_in', label: 'Снаружи внутрь' },
];

const DOOR_LAYOUTS = [
  { value: 'left', label: 'Слева' },
  { value: 'right', label: 'Справа' },
  { value: 'both', label: 'Справа и слева' },
];

const COMPENSATORS = [
  { value: 'lower', label: 'Снизу' },
  { value: 'upper', label: 'Сверху' },
  { value: 'both', label: 'Сверху и снизу' },
  { value: 'none', label: 'Без комп. профиля' },
];

function BookBlock({
  title,
  children,
  preliminary = false,
}: {
  title: string;
  children: ReactNode;
  preliminary?: boolean;
}) {
  return (
    <section className="rounded-2xl border border-tint/25 bg-black/5 p-4" data-book-form-block={title}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h4 className="text-[10px] font-bold uppercase tracking-widest text-accent/55">{title}</h4>
        {preliminary && (
          <span className="rounded-full border border-amber-400/35 bg-amber-500/10 px-2 py-1 text-[9px] font-bold uppercase tracking-wider text-amber-300">
            Предварительно
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

function ChoiceButtons({
  value,
  options,
  onChange,
}: {
  value?: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map(option => (
        <button
          type="button"
          key={option.value}
          data-book-choice={option.value}
          onClick={() => onChange(option.value)}
          className={`min-w-[100px] flex-1 rounded-xl border px-3 py-2 text-xs font-bold transition-all ${
            value === option.value
              ? 'border-accent/55 bg-accent/12 text-accent'
              : 'border-tint/25 bg-black/10 text-fg/50 hover:border-tint/50'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

type DoorSide = 'left' | 'right';
type RelativeSide = 'left' | 'right';

const DOOR_FIELDS: Record<DoorSide, {
  hardware: keyof Section;
  opening: keyof Section;
  width: keyof Section;
  fixed: Record<RelativeSide, { enabled: keyof Section; width: keyof Section }>;
}> = {
  left: {
    hardware: 'bookLeftDoorHardware',
    opening: 'bookLeftDoorOpening',
    width: 'bookLeftDoorWidth',
    fixed: {
      left: { enabled: 'bookLeftFixedLeftEnabled', width: 'bookLeftFixedLeftWidth' },
      right: { enabled: 'bookLeftFixedRightEnabled', width: 'bookLeftFixedRightWidth' },
    },
  },
  right: {
    hardware: 'bookRightDoorHardware',
    opening: 'bookRightDoorOpening',
    width: 'bookRightDoorWidth',
    fixed: {
      left: { enabled: 'bookRightFixedLeftEnabled', width: 'bookRightFixedLeftWidth' },
      right: { enabled: 'bookRightFixedRightEnabled', width: 'bookRightFixedRightWidth' },
    },
  },
};

function FixedPanelControl({
  doorSide,
  relativeSide,
  section,
  update,
}: {
  doorSide: DoorSide;
  relativeSide: RelativeSide;
  section: Section;
  update: (updates: Partial<Section>) => void;
}) {
  const fields = DOOR_FIELDS[doorSide].fixed[relativeSide];
  const enabled = Boolean(section[fields.enabled]);
  const width = section[fields.width] as number | undefined;
  return (
    <div className="space-y-2 rounded-lg border border-tint/20 bg-black/5 p-2.5" data-book-fixed={`${doorSide}-${relativeSide}`}>
      <Checkbox
        checked={enabled}
        onChange={() => update({
          [fields.enabled]: !enabled,
          [fields.width]: width || 500,
        } as Partial<Section>)}
        label={`Глухая панель ${relativeSide === 'left' ? 'слева' : 'справа'} от двери`}
      />
      {enabled && (
        <div className="space-y-1.5 pl-7">
          <label className={LBL}>Ширина глухой панели, мм</label>
          <input
            type="number"
            min={4}
            step={0.1}
            required
            value={width ?? ''}
            onChange={event => update({
              [fields.width]: event.target.value === '' ? undefined : Number(event.target.value),
            } as Partial<Section>)}
            className={INP}
            data-book-fixed-width={`${doorSide}-${relativeSide}`}
          />
        </div>
      )}
    </div>
  );
}

function DoorSettings({
  side,
  section,
  update,
}: {
  side: DoorSide;
  section: Section;
  update: (updates: Partial<Section>) => void;
}) {
  const fields = DOOR_FIELDS[side];
  const hardware = section[fields.hardware] as string | undefined;
  const opening = section[fields.opening] as string | undefined;
  const width = section[fields.width] as number | undefined;
  return (
    <div className="rounded-xl border border-tint/25 bg-hi/5 p-3" data-book-door={side}>
      <h5 className="mb-3 text-xs font-bold text-fg/75">
        {side === 'left' ? 'Левая дверь' : 'Правая дверь'}
      </h5>
      <div className="space-y-3">
        <div className="space-y-1.5">
          <label className={LBL}>Ширина двери, мм (необязательно)</label>
          <input
            type="number"
            min={4}
            step={0.1}
            value={width ?? ''}
            onChange={event => update({
              [fields.width]: event.target.value === '' ? undefined : Number(event.target.value),
            } as Partial<Section>)}
            className={INP}
            placeholder="Рассчитать автоматически"
            data-book-door-width={side}
          />
        </div>
        <div className="space-y-1.5">
          <label className={LBL}>Фурнитура</label>
          <ChoiceButtons
            value={hardware || 'handle'}
            options={[
              { value: 'handle', label: 'Стеклянная ручка' },
              { value: 'lock', label: 'Замок с ручкой' },
            ]}
            onChange={value => update({
              [fields.hardware]: value,
              doorType: value === 'lock' ? 'Тип 4 / замок' : 'Тип 1 / ручка',
            } as Partial<Section>)}
          />
        </div>
        <div className="space-y-1.5">
          <label className={LBL}>Открывание</label>
          <select
            value={opening || 'inside_in'}
            onChange={event => {
              const next = event.target.value;
              update({
                [fields.opening]: next,
                doorOpening: OPENINGS.find(item => item.value === next)?.label,
              } as Partial<Section>);
            }}
            className={SEL}
            data-book-opening={side}
          >
            {OPENINGS.map(item => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </div>
        <FixedPanelControl doorSide={side} relativeSide="left" section={section} update={update} />
        <FixedPanelControl doorSide={side} relativeSide="right" section={section} update={update} />
      </div>
    </div>
  );
}

export function BookSystemTab({
  s,
  update,
}: {
  s: Section;
  update: (updates: Partial<Section>) => void;
}) {
  const rawLayout = s.doorSide || (s.doors === 2 ? 'both' : 'right');
  const doorLayout = rawLayout === 'none' ? 'right' : rawLayout;
  const hasLeftDoor = doorLayout === 'left' || doorLayout === 'both';
  const hasRightDoor = doorLayout === 'right' || doorLayout === 'both';
  const extraDoorPanelOptions = bookExtraDoorPanelOptions({
    panelCount: s.panels,
    doorLayout,
    leftFixedLeftEnabled: s.bookLeftFixedLeftEnabled,
    leftFixedRightEnabled: s.bookLeftFixedRightEnabled,
    rightFixedLeftEnabled: s.bookRightFixedLeftEnabled,
    rightFixedRightEnabled: s.bookRightFixedRightEnabled,
  });
  const selectedExtraDoorPanel = extraDoorPanelOptions.includes(s.bookExtraDoorPanel || 0)
    ? s.bookExtraDoorPanel
    : extraDoorPanelOptions[0];
  const hasPreliminaryFeatures = Boolean(
    s.angleLeft
    || s.angleRight
    || s.bookExtraDoorEnabled
    || (s.bookSystem && s.bookSystem !== 'B25'),
  );

  const changeDoorLayout = (layout: string) => {
    const doors = layout === 'both' ? 2 : 1;
    update({
      doorSide: layout,
      doors,
      bookSubtype: 'doors',
      bookSystem: s.bookSystem || 'B25',
      bookLeftDoorHardware: layout === 'left' || layout === 'both'
        ? s.bookLeftDoorHardware || 'handle'
        : undefined,
      bookRightDoorHardware: layout === 'right' || layout === 'both'
        ? s.bookRightDoorHardware || 'handle'
        : undefined,
      bookLeftDoorOpening: layout === 'left' || layout === 'both'
        ? s.bookLeftDoorOpening || 'inside_in'
        : undefined,
      bookRightDoorOpening: layout === 'right' || layout === 'both'
        ? s.bookRightDoorOpening || 'inside_in'
        : undefined,
    });
  };

  return (
    <div className="space-y-4" data-book-form data-book-system="B25">
      <BookBlock title="Основные параметры">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label className={LBL}>Количество панелей, включая двери</label>
            <input
              type="number"
              min={2}
              step={1}
              value={s.panels || ''}
              onChange={event => update({ panels: Math.max(0, Number(event.target.value)) })}
              className={INP}
              data-book-panel-count
            />
          </div>
          <div className="space-y-1.5">
            <label className={LBL}>До препятствия, мм</label>
            <input
              type="number"
              min={0}
              step={0.1}
              value={s.bookObstacleDistance ?? ''}
              onChange={event => update({
                bookObstacleDistance: event.target.value === '' ? undefined : Number(event.target.value),
              })}
              className={INP}
              placeholder="0"
              data-book-obstacle-distance
            />
          </div>
          <div className="space-y-1.5">
            <label className={LBL}>Высота ручки, мм</label>
            <input
              type="number"
              min={0}
              max={s.height}
              step={0.1}
              value={s.bookHandleHeight ?? ''}
              onChange={event => update({
                bookHandleHeight: event.target.value === '' ? undefined : Number(event.target.value),
              })}
              className={INP}
              placeholder="1000"
              data-book-handle-height
            />
          </div>
        </div>
      </BookBlock>

      <BookBlock title="Двери">
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className={LBL}>Расположение дверей</label>
            <ChoiceButtons value={doorLayout} options={DOOR_LAYOUTS} onChange={changeDoorLayout} />
          </div>
          <div className={`grid grid-cols-1 gap-3 ${hasLeftDoor && hasRightDoor ? 'sm:grid-cols-2' : ''}`}>
            {hasLeftDoor && <DoorSettings side="left" section={s} update={update} />}
            {hasRightDoor && <DoorSettings side="right" section={s} update={update} />}
          </div>
          {doorLayout === 'both' && (
            <div className="space-y-1.5">
              <label className={LBL}>Подвижных панелей в левом сборе</label>
              <select
                value={s.bookLeftStackPanels ?? Math.max(1, Math.floor(s.panels / 2))}
                onChange={event => update({ bookLeftStackPanels: Number(event.target.value) })}
                className={SEL}
                data-book-left-stack
              >
                {Array.from({ length: Math.max(1, s.panels - 1) }, (_, index) => index + 1).map(count => (
                  <option key={count} value={count}>{count}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </BookBlock>

      <BookBlock title="Компенсирующие профили">
        <ChoiceButtons
          value={s.compensator || 'lower'}
          options={COMPENSATORS}
          onChange={compensator => update({ compensator })}
        />
      </BookBlock>

      <BookBlock title="Дополнительная двигающаяся дверь" preliminary>
        <div className="space-y-3 rounded-xl border border-tint/20 p-3">
          <div className="rounded-xl border border-amber-400/30 bg-amber-500/8 px-3 py-2 text-xs text-amber-200" data-book-preliminary-note>
            Дополнительная двигающаяся дверь пока рассчитывается предварительно и блокирует производственные документы.
          </div>
          <Checkbox
            checked={Boolean(s.bookExtraDoorEnabled)}
            onChange={() => update({
              bookExtraDoorEnabled: !s.bookExtraDoorEnabled,
              bookExtraDoorPanel: selectedExtraDoorPanel,
              bookExtraDoorWidth: s.bookExtraDoorWidth || 700,
              bookExtraDoorOpening: s.bookExtraDoorOpening || 'inside_in',
            })}
            label="Добавить дополнительную двигающуюся дверь"
            disabled={!s.bookExtraDoorEnabled && extraDoorPanelOptions.length === 0}
          />
          {extraDoorPanelOptions.length === 0 && (
            <div className="pl-7 text-[10px] font-bold text-amber-300">
              Нет обычной подвижной панели, которую можно заменить дверью.
            </div>
          )}
          {s.bookExtraDoorEnabled && extraDoorPanelOptions.length > 0 && (
            <div className="grid grid-cols-1 gap-3 pl-7 sm:grid-cols-3">
              <div className="space-y-1.5">
                <label className={LBL}>Физическая панель №</label>
                <select
                  value={selectedExtraDoorPanel}
                  onChange={event => update({ bookExtraDoorPanel: Number(event.target.value) })}
                  className={SEL}
                  data-book-extra-door-panels={extraDoorPanelOptions.join(',')}
                >
                  {extraDoorPanelOptions.map(number => (
                    <option key={number} value={number}>{number}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className={LBL}>Ширина, мм</label>
                <input
                  type="number"
                  min={4}
                  max={850}
                  step={0.1}
                  value={s.bookExtraDoorWidth ?? ''}
                  onChange={event => update({
                    bookExtraDoorWidth: event.target.value === '' ? undefined : Number(event.target.value),
                  })}
                  className={INP}
                />
              </div>
              <div className="space-y-1.5">
                <label className={LBL}>Открывание</label>
                <select
                  value={s.bookExtraDoorOpening || 'inside_in'}
                  onChange={event => update({ bookExtraDoorOpening: event.target.value })}
                  className={SEL}
                >
                  {OPENINGS.map(item => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </div>
            </div>
          )}
        </div>
      </BookBlock>

      {hasPreliminaryFeatures && (
        <div className="flex gap-2 rounded-xl border border-amber-400/40 bg-amber-500/12 px-4 py-3 text-sm font-bold text-amber-200" data-book-preliminary-warning>
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>Активна предварительная конфигурация — производственные документы недоступны.</span>
        </div>
      )}
    </div>
  );
}
