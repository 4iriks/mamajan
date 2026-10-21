"""Legacy write APIs are retired; no hidden backdoor may update construction pricing."""
import pytest

@pytest.mark.parametrize('method,path', [
 ('get', '/api/pricing/rules'), ('post', '/api/pricing/rules'),
 ('post', '/api/pricing/rules/preview'), ('post', '/api/pricing/rule-bindings/apply'),
 ('post', '/api/catalog/pricing/bulk/preview'), ('post', '/api/catalog/pricing/bulk/apply'),
 ('post', '/api/pricing/catalog/bulk/preview'), ('post', '/api/pricing/catalog/bulk/apply'),
 ('get', '/api/catalog/system-markups'), ('put', '/api/catalog/system-markups/SLIDE_1'),
 ('get', '/api/pricing/price-groups'), ('post', '/api/pricing/price-groups'),
 ('get', '/api/catalog/construction-price-groups'),
])
def test_removed_price_mutations_are_unavailable(client, admin_headers, method, path):
    response = getattr(client, method)(path, headers=admin_headers)
    assert response.status_code == 404
