import type { HardwareCatalogOption } from '../../api/catalog';

const naturalCollator = new Intl.Collator('ru', {
  numeric: true,
  sensitivity: 'base',
});

export function naturalCatalogCompare(
  left: Pick<HardwareCatalogOption, 'sku' | 'name'>,
  right: Pick<HardwareCatalogOption, 'sku' | 'name'>,
) {
  return naturalCollator.compare(left.sku, right.sku)
    || naturalCollator.compare(left.name, right.name);
}

export function filterCatalogOptions(
  rows: HardwareCatalogOption[],
  query: string,
) {
  const needle = query.trim().toLocaleLowerCase('ru');
  return rows
    .filter(row => row.isActive)
    .filter(row => !needle || `${row.sku} ${row.name}`.toLocaleLowerCase('ru').includes(needle))
    .sort(naturalCatalogCompare);
}
