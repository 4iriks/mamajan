import { INP, LBL, SEL, Section } from './types';
import { RadioList, ToggleGroup } from './FormInputs';
import {
  LIFT_DEFAULT_CABLE_SIDE,
  LIFT_DEFAULT_CONTROL,
  LIFT_DEFAULT_FILLING,
  LIFT_DEFAULT_OPENING,
  LIFT_FILLING_OPTIONS,
  LIFT_SPLIT_OPENING,
  liftOpeningOptions,
} from './liftConfig';

function PaintingFields({
  section,
  update,
}: {
  section: Section;
  update: (updates: Partial<Section>) => void;
}) {
  const setPaintingType = (paintingType: Section['paintingType']) => {
    update({
      paintingType,
      ...(paintingType.includes('RAL') && !section.ralColor
        ? { ralColor: '9016 МАТОВЫЙ' }
        : {}),
    });
  };

  return (
    <div className="space-y-1.5">
      <label className={LBL}>Окрашивание</label>
      <div className="space-y-1.5">
        {(['RAL стандарт', 'RAL нестандарт', 'Анодированный'] as const).map(type => (
          <button
            key={type}
            type="button"
            onClick={() => setPaintingType(type)}
            className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2 text-left transition-all ${
              section.paintingType === type
                ? 'border-accent/50 bg-accent/10 text-accent'
                : 'border-tint/20 bg-black/10 text-fg/50 hover:border-tint/50'
            }`}
          >
            <span
              className={`flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border ${
                section.paintingType === type ? 'border-accent' : 'border-hi/10'
              }`}
            >
              {section.paintingType === type && <span className="h-2 w-2 rounded-full bg-accent" />}
            </span>
            <span className="text-xs font-medium">{type}</span>
          </button>
        ))}
      </div>

      {section.paintingType.includes('RAL') && (
        <div className="mt-2 space-y-1.5">
          <label className={LBL}>Цвет RAL</label>
          <input
            type="text"
            value={section.ralColor || ''}
            onChange={event => update({ ralColor: event.target.value })}
            className={INP}
            placeholder="Напр. 9016 МАТОВЫЙ"
          />
        </div>
      )}
    </div>
  );
}

export function LiftMainTab({
  s,
  update,
}: {
  s: Section;
  update: (updates: Partial<Section>) => void;
}) {
  const fillingType = s.liftFillingType || LIFT_DEFAULT_FILLING;
  const isCustom = fillingType === 'ДРУГОЕ 8мм' || fillingType === 'ДРУГОЕ 20мм';

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-6">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className={LBL}>Секция №</label>
            <input
              type="number"
              min="1"
              value={s.name.replace(/\D/g, '')}
              onChange={event => update({ name: `Секция ${event.target.value}` })}
              className={INP}
            />
          </div>
          <div className="space-y-1.5">
            <label className={LBL}>Кол-во, шт</label>
            <input
              type="number"
              min="1"
              value={s.quantity || ''}
              onChange={event => update({ quantity: Number.parseInt(event.target.value, 10) || 0 })}
              className={INP}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className={LBL}>Ширина, мм</label>
            <input
              type="number"
              min="1"
              value={s.width || ''}
              onChange={event => update({ width: Number.parseInt(event.target.value, 10) || 0 })}
              className={INP}
            />
          </div>
          <div className="space-y-1.5">
            <label className={LBL}>Высота, мм</label>
            <input
              type="number"
              min="1"
              value={s.height || ''}
              onChange={event => update({ height: Number.parseInt(event.target.value, 10) || 0 })}
              className={INP}
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <label className={LBL}>Заполнение</label>
          <select
            value={fillingType}
            onChange={event => {
              const nextType = event.target.value;
              const nextIsCustom = nextType === 'ДРУГОЕ 8мм' || nextType === 'ДРУГОЕ 20мм';
              update({
                liftFillingType: nextType,
                ...(!nextIsCustom ? { liftFillingCustom: undefined } : {}),
              });
            }}
            className={SEL}
          >
            {LIFT_FILLING_OPTIONS.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>

          {isCustom && (
            <input
              type="text"
              value={s.liftFillingCustom || ''}
              onChange={event => update({ liftFillingCustom: event.target.value })}
              onBlur={event => update({ liftFillingCustom: event.currentTarget.value.trim() || undefined })}
              className={INP}
              placeholder="Введите название заполнения"
              autoComplete="off"
            />
          )}
        </div>
      </div>

      <PaintingFields section={s} update={update} />
    </div>
  );
}

export function LiftSystemTab({
  s,
  update,
}: {
  s: Section;
  update: (updates: Partial<Section>) => void;
}) {
  const panels = Math.min(4, Math.max(2, s.panels || 2));
  const controlType = s.liftControlType || LIFT_DEFAULT_CONTROL;
  const openingType = s.liftOpeningType || LIFT_DEFAULT_OPENING;
  const openingOptions = liftOpeningOptions(panels);

  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-8">
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Количество панелей</label>
          <ToggleGroup
            value={String(panels)}
            options={['2', '3', '4']}
            onChange={value => {
              const nextPanels = Number.parseInt(value, 10);
              update({
                panels: nextPanels,
                ...(nextPanels !== 4 && openingType === LIFT_SPLIT_OPENING
                  ? { liftOpeningType: LIFT_DEFAULT_OPENING }
                  : {}),
              });
            }}
          />
        </div>

        <div className="space-y-2">
          <label className={LBL}>Вариант открывания</label>
          <RadioList
            value={openingOptions.includes(openingType) ? openingType : LIFT_DEFAULT_OPENING}
            options={openingOptions}
            onChange={value => update({ liftOpeningType: value || LIFT_DEFAULT_OPENING })}
          />
        </div>
      </div>

      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Управление электроприводом</label>
          <ToggleGroup
            value={controlType}
            options={['Пульт ДУ', 'Кнопка']}
            onChange={value => update({ liftControlType: value })}
          />
          {controlType === 'Пульт ДУ' && (
            <div
              className="mt-3 space-y-3 rounded-xl border border-tint/25 bg-black/10 p-3"
              data-lift-remote-counts
            >
              <label className="grid grid-cols-[1fr_110px] items-center gap-3 text-sm text-fg/70">
                <span>Пульт 1 канал, шт</span>
                <input
                  data-lift-remote-count="1"
                  type="number"
                  min={0}
                  step={1}
                  value={s.liftRemote1chQty ?? 0}
                  onChange={event => update({
                    liftRemote1chQty: Math.max(0, Number.parseInt(event.target.value || '0', 10) || 0),
                  })}
                  className={INP}
                />
              </label>
              <label className="grid grid-cols-[1fr_110px] items-center gap-3 text-sm text-fg/70">
                <span>Пульт 6 каналов, шт</span>
                <input
                  data-lift-remote-count="6"
                  type="number"
                  min={0}
                  step={1}
                  value={s.liftRemote6chQty ?? 0}
                  onChange={event => update({
                    liftRemote6chQty: Math.max(0, Number.parseInt(event.target.value || '0', 10) || 0),
                  })}
                  className={INP}
                />
              </label>
              <p className={`text-[11px] leading-relaxed ${
                (s.liftRemote1chQty ?? 0) + (s.liftRemote6chQty ?? 0) === 0
                  ? 'text-amber-400/80'
                  : 'text-fg/40'
              }`}>
                {(s.liftRemote1chQty ?? 0) + (s.liftRemote6chQty ?? 0) === 0
                  ? 'Количество пультов на весь проект. Укажите нужное количество.'
                  : 'Вы меняете общее количество пультов в проекте, а не в конкретной секции.'}
              </p>
            </div>
          )}
        </div>

        <div className="space-y-2">
          <label className={LBL}>Ввод кабеля</label>
          <ToggleGroup
            value={s.liftCableSide || LIFT_DEFAULT_CABLE_SIDE}
            options={['Слева', 'Справа']}
            onChange={value => update({ liftCableSide: value })}
          />
        </div>
      </div>
    </div>
  );
}
