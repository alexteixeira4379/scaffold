import importlib.util
from pathlib import Path

import sqlalchemy as sa


def test_copy_only_migration_is_idempotent_and_preserves_rules(monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'migrations/core/versions/0039_onboarding_inline_copy.py'
    spec = importlib.util.spec_from_file_location('migration_0039', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    metadata = sa.MetaData()
    table = sa.Table('resume_build_steps', metadata, sa.Column('id', sa.Integer, primary_key=True),
                     sa.Column('options', sa.JSON), sa.Column('active', sa.Boolean))
    engine = sa.create_engine('sqlite://')
    metadata.create_all(engine)
    question = 'Pode enviar seu *currículo em PDF* ou contar por *áudio ou texto*.'
    original = {'question': question, 'agent_prompt': 'preserve', 'action': 'preserve', 'max_length': 8000}
    with engine.begin() as conn:
        conn.execute(table.insert().values(id=42, active=False, options=original))
        monkeypatch.setattr(migration.op, 'get_bind', lambda: conn)
        migration.upgrade()
        migration.upgrade()
        row = conn.execute(sa.select(table)).mappings().one()
        assert row['id'] == 42 and row['active'] is False
        assert row['options'] == {**original, 'question': 'Pode enviar seu currículo em `PDF` ou contar por `áudio` ou `texto`.'}
        migration.downgrade()
        assert conn.scalar(sa.select(table.c.options)) == original
