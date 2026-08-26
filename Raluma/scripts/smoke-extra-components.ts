import assert from 'node:assert/strict';

import type { HardwareCatalogOption } from '../src/api/catalog';
import {
  filterCatalogOptions,
  naturalCatalogCompare,
} from '../src/components/editor/extraComponentsCatalog';
import {
  cloneExtraComponents,
  stringifyExtraComponents,
} from '../src/components/editor/converters';

const option = (
  id: number,
  sku: string,
  name: string,
  isActive = true,
): HardwareCatalogOption => ({
  id,
  sku,
  name,
  category: sku.startsWith('RS') ? 'profile' : 'component',
  unit: 'шт',
  imageFile: '',
  isActive,
});

const catalog = [
  option(1, 'RS10', 'Профиль десятый'),
  option(2, 'RS2', 'Профиль второй'),
  option(3, 'RU004', 'Ролик нижний'),
  option(4, 'RU003', 'Ролик верхний'),
  option(5, 'RS1', 'Архивная позиция', false),
];

assert.deepEqual(
  [...catalog].filter(row => row.isActive).sort(naturalCatalogCompare).map(row => row.sku),
  ['RS2', 'RS10', 'RU003', 'RU004'],
  'catalog options must use natural SKU-first order',
);
assert.deepEqual(
  filterCatalogOptions(catalog, 'ролик').map(row => row.sku),
  ['RU003', 'RU004'],
  'search must match the Russian item name',
);
assert.deepEqual(
  filterCatalogOptions(catalog, 'rs10').map(row => row.sku),
  ['RS10'],
  'search must be case-insensitive and match SKU',
);
assert.equal(
  filterCatalogOptions(catalog, 'архив').length,
  0,
  'inactive catalog rows must stay hidden',
);

const savedExtras = [{
  id: 'saved-1',
  sku: 'RU005',
  name: 'Ролик',
  color: '',
  size: '',
  qty: '2',
  unit: 'шт',
  deliveryStage: 'both' as const,
}];
const modalDraft = cloneExtraComponents(savedExtras);
modalDraft[0].qty = '9';
assert.equal(
  savedExtras[0].qty,
  '2',
  'editing or closing the modal draft must not mutate saved project extras',
);

const manualSnapshot = JSON.parse(stringifyExtraComponents([{
  sku: '',
  name: 'Уголок монтажный',
  color: 'RAL 9005',
  size: '1200 мм',
  qty: '3',
}]))[0];
assert.equal(manualSnapshot.category, 'component');
assert.equal(manualSnapshot.requires_paint, true);
assert.equal(manualSnapshot.name, 'Уголок монтажный');
assert.equal(
  JSON.parse(stringifyExtraComponents([{
    sku: '',
    name: '',
    color: '',
    size: '',
    qty: '1',
  }])).length,
  0,
  'an untouched manual row must not be persisted',
);

const values = new Map<string, string>();
const memoryStorage: Storage = {
  get length() { return values.size; },
  clear: () => values.clear(),
  getItem: key => values.get(key) ?? null,
  key: index => [...values.keys()][index] ?? null,
  removeItem: key => { values.delete(key); },
  setItem: (key, value) => { values.set(key, value); },
};
Object.defineProperty(globalThis, 'localStorage', { value: memoryStorage });

const localProjects = await import('../src/api/localProjects');
memoryStorage.setItem(localProjects.LOCAL_PROJECTS_KEY, JSON.stringify([{
  id: 101,
  number: 'LEGACY-1',
  customer: 'Старый заказчик',
  created_at: '2026-01-01T00:00:00.000Z',
  updated_at: '2026-01-01T00:00:00.000Z',
  created_by: 0,
  sections: [],
}]));

const legacy = localProjects.getLocalProject(101);
assert.equal(legacy.hardware_installation, 'not_installed');
assert.equal(legacy.extra_components, '[]');

const created = localProjects.createLocalProject({
  number: 'NEW-1',
  customer: 'Новый заказчик',
});
assert.equal(created.hardware_installation, 'installed');
assert.equal(created.extra_components, '[]');

const legacyComponents = JSON.stringify([{ sku: 'RS1005', qty: '2', unit: 'шт' }]);
const savedComponents = JSON.stringify([{ sku: 'RS1005', qty: 2, unit: 'шт' }]);
localProjects.updateLocalProject(created.id, {
  hardware_installation: 'not_installed',
  extra_components: legacyComponents,
});
const copied = localProjects.copyLocalProject(created.id);
assert.equal(copied.hardware_installation, 'not_installed');
assert.equal(copied.extra_components, savedComponents);

console.log('Extra-components and local-project migration smoke checks passed.');
