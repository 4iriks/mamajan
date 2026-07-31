import { AlertTriangle } from 'lucide-react';
import type { ReactNode } from 'react';

import { BOOK_PROFILE_SYSTEMS, bookExtraDoorPanelOptions } from '../../constants/book';
import { Checkbox } from './FormInputs';
import { INP, LBL, SEL, Section } from './types';


const OPENINGS = [
  { value: 'inside_in', label: 'Изнутри внутрь' },
  { value: 'inside_out', label: 'Изнутри наружу' },
  { value: 'outside_out', label: 'Снаружи наружу' },
  { value: 'outside_in', label: 'Снаружи внутрь' },
];

const DOOR_LAYOUTS = [
  { value: 'none', label: 'Без дверей' },
  { value: 'left', label: 'Слева' },
  { value: 'right', label: 'Справа' },
  { value: 'both', label: 'С двух сторон' },
];

const COMPENSATORS = [
  { value: 'lower', label: 'Нижний' },
  { value: 'upper', label: 'Верхний' },
  { value: 'both', label: 'Оба' },
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

function DoorSettings({
  side,
  hardware,
  opening,
  update,
}: {
  side: 'left' | 'right';
  hardware?: string;
  opening?: string;
  update: (updates: Partial<Section>) => void;
}) {
  const hardwareField = side === 'left' ? 'bookLeftDoorHardware' : 'bookRightDoorHardware';
  const openingField = side === 'left' ? 'bookLeftDoorOpening' : 'bookRightDoorOpening';
  return (
    <div className="rounded-xl border border-tint/25 bg-hi/5 p-3" data-book-door={side}>
      <h5 className="mb-3 text-xs font-bold text-fg/75">
        {side === 'left' ? 'Левая дверь' : 'Правая дверь'}
      </h5>
      <div className="space-y-3">
        <div className="space-y-1.5">
          <label className={LBL}>Фурнитура</label>
          <ChoiceButtons
            value={hardware || 'handle'}
            options={[
              { value: 'handle', label: 'Стеклянная ручка' },
              { value: 'lock', label: 'Замок с ручкой' },
            ]}
            onChange={value => update({
              [hardwareField]: value,
              doorType: value === 'lock' ? 'Тип 4 / замок' : 'Тип 1 / ручка',
            })}
          />
        </div>
        <div className="space-y-1.5">
          <label className={LBL}>Открывание</label>
          <select
            value={opening || 'inside_in'}
            onChange={event => {
              const next = event.target.value;
              update({
                [openingField]: next,
                doorOpening: OPENINGS.find(item => item.value === next)?.label,
              });
            }}
            className={SEL}
            data-book-opening={side}
          >
            {OPENINGS.map(item => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </div>
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
  const doorLayout = s.doorSide || (s.doors === 2 ? 'both' : s.doors === 1 ? 'right' : 'none');
  const hasLeftDoor = doorLayout === 'left' || doorLayout === 'both';
  const hasRightDoor = doorLayout === 'right' || doorLayout === 'both';
  const extraDoorPanelOptions = bookExtraDoorPanelOptions({
    panelCount: s.panels,
    doorLayout,
    extraFixedEnabled: s.bookExtraFixedEnabled,
    extraFixedSide: s.bookExtraFixedSide,
  });
  const physicalPanelCount = s.panels + (s.bookExtraFixedEnabled ? 1 : 0);
  const selectedExtraDoorPanel = extraDoorPanelOptions.includes(
    s.bookExtraDoorPanel || 0,
  )
    ? s.bookExtraDoorPanel
    : extraDoorPanelOptions[0];
  const hasPreliminaryFeatures = Boolean(
    s.angleLeft
    || s.angleRight
    || s.bookExtraFixedEnabled
    || s.bookExtraDoorEnabled
    || (s.bookSystem && s.bookSystem !== 'B25'),
  );

  const changeDoorLayout = (layout: string) => {
    const doors = layout === 'both' ? 2 : layout === 'none' ? 0 : 1;
    update({
      doorSide: layout,
      doors,
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
    <div className="space-y-4" data-book-form>
      <BookBlock title="Основные параметры">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label className={LBL}>Количество панелей</label>
            <select
              value={s.panels}
              onChange={event => update({ panels: Number(event.target.value) })}
              className={SEL}
              data-book-panel-count
            >
              {[2, 3, 4, 5, 6].map(count => (
                <option key={count} value={count}>{count}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className={LBL}>Система книжки</label>
            <select
              value={s.bookSystem || 'B25'}
              onChange={event => update({
                bookSystem: event.target.value as Section['bookSystem'],
              })}
              className={SEL}
              data-book-profile-system
            >
              {BOOK_PROFILE_SYSTEMS.map(system => (
                <option key={system.value} value={system.value}>{system.label}</option>
              ))}
            </select>
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
          {(hasLeftDoor || hasRightDoor) && (
            <div className={`grid grid-cols-1 gap-3 ${hasLeftDoor && hasRightDoor ? 'sm:grid-cols-2' : ''}`}>
              {hasLeftDoor && (
                <DoorSettings
                  side="left"
                  hardware={s.bookLeftDoorHardware}
                  opening={s.bookLeftDoorOpening}
                  update={update}
                />
              )}
              {hasRightDoor && (
                <DoorSettings
                  side="right"
                  hardware={s.bookRightDoorHardware}
                  opening={s.bookRightDoorOpening}
                  update={update}
                />
              )}
            </div>
          )}
          {doorLayout === 'both' && (
            <div className="space-y-1.5">
              <label className={LBL}>Физических панелей в левом сборе</label>
              <select
                value={s.bookLeftStackPanels ?? Math.max(1, Math.floor(s.panels / 2))}
                onChange={event => update({ bookLeftStackPanels: Number(event.target.value) })}
                className={SEL}
                data-book-left-stack
              >
                {Array.from({ length: Math.max(1, physicalPanelCount - 1) }, (_, index) => index + 1).map(count => (
                  <option key={count} value={count}>{count}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </BookBlock>

      <BookBlock title="Компенсаторы">
        <ChoiceButtons
          value={s.compensator || 'lower'}
          options={COMPENSATORS}
          onChange={compensator => update({ compensator })}
        />
      </BookBlock>

      <BookBlock title="Дополнительные элементы и углы" preliminary>
        <div className="space-y-4">
          <div className="rounded-xl border border-amber-400/30 bg-amber-500/8 px-3 py-2 text-xs text-amber-200" data-book-preliminary-note>
            Углы, дополнительная дверь и глухая панель рассчитываются предварительно.
            Производственные документы для них заблокированы.
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className={LBL}>Угол слева, °</label>
              <input
                type="number"
                min={0}
                max={180}
                step={0.1}
                value={s.angleLeft ?? ''}
                onChange={event => update({
                  angleLeft: event.target.value === '' ? undefined : Number(event.target.value),
                })}
                className={INP}
                placeholder="0"
                data-book-angle="left"
              />
            </div>
            <div className="space-y-1.5">
              <label className={LBL}>Угол справа, °</label>
              <input
                type="number"
                min={0}
                max={180}
                step={0.1}
                value={s.angleRight ?? ''}
                onChange={event => update({
                  angleRight: event.target.value === '' ? undefined : Number(event.target.value),
                })}
                className={INP}
                placeholder="0"
                data-book-angle="right"
              />
            </div>
          </div>

          <div className="space-y-3 rounded-xl border border-tint/20 p-3">
            <Checkbox
              checked={Boolean(s.bookExtraFixedEnabled)}
              onChange={() => update({
                bookExtraFixedEnabled: !s.bookExtraFixedEnabled,
                bookExtraFixedSide: s.bookExtraFixedSide || 'left',
                bookExtraFixedWidth: s.bookExtraFixedWidth || 500,
              })}
              label="Дополнительная глухая панель"
            />
            {s.bookExtraFixedEnabled && (
              <div className="grid grid-cols-2 gap-3 pl-7">
                <div className="space-y-1.5">
                  <label className={LBL}>Сторона</label>
                  <select
                    value={s.bookExtraFixedSide || 'left'}
                    onChange={event => update({ bookExtraFixedSide: event.target.value })}
                    className={SEL}
                  >
                    <option value="left">Слева</option>
                    <option value="right">Справа</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className={LBL}>Ширина, мм</label>
                  <input
                    type="number"
                    min={1}
                    step={0.1}
                    value={s.bookExtraFixedWidth ?? ''}
                    onChange={event => update({
                      bookExtraFixedWidth: event.target.value === '' ? undefined : Number(event.target.value),
                    })}
                    className={INP}
                  />
                </div>
              </div>
            )}
          </div>

          <div className="space-y-3 rounded-xl border border-tint/20 p-3">
            <Checkbox
              checked={Boolean(s.bookExtraDoorEnabled)}
              onChange={() => update({
                bookExtraDoorEnabled: !s.bookExtraDoorEnabled,
                bookExtraDoorPanel: selectedExtraDoorPanel,
                bookExtraDoorWidth: s.bookExtraDoorWidth || 700,
                bookExtraDoorOpening: s.bookExtraDoorOpening || 'inside_in',
              })}
              label="Дополнительная двигающаяся дверь"
              disabled={!s.bookExtraDoorEnabled && extraDoorPanelOptions.length === 0}
            />
            {extraDoorPanelOptions.length === 0 && (
              <div className="pl-7 text-[10px] font-bold text-amber-300">
                Нет обычной подвижной панели: отключите дополнительную дверь
                или освободите панель, занятую крайней дверью.
              </div>
            )}
            {s.bookExtraDoorEnabled && extraDoorPanelOptions.length > 0 && (
              <div className="grid grid-cols-1 gap-3 pl-7 sm:grid-cols-3">
                <div className="space-y-1.5">
                  <label className={LBL}>Панель №</label>
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
                    min={1}
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
        </div>
      </BookBlock>

      {hasPreliminaryFeatures && (
        <div
          className="flex gap-2 rounded-xl border border-amber-400/40 bg-amber-500/12 px-4 py-3 text-sm font-bold text-amber-200"
          data-book-preliminary-warning
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>Активна предварительная конфигурация — производственные документы недоступны.</span>
        </div>
      )}
    </div>
  );
}
