from sqlalchemy import inspect

from database import engine


def test_legacy_section_template_api_is_removed(client, admin_headers):
    assert client.get("/api/section-templates").status_code == 404
    assert client.post(
        "/api/section-templates",
        headers=admin_headers,
        json={
            "name": "Старый шаблон",
            "system": "СЛАЙД 1 ряд",
            "template_data": {},
        },
    ).status_code == 404
    assert not inspect(engine).has_table("section_templates")
