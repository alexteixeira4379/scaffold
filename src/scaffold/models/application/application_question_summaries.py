"""Lightweight question coverage per concrete instrumented attempt."""
from sqlalchemy import BigInteger,Column,DateTime,Integer,String,Table,func
from scaffold.base import CoreBase
application_question_summaries = Table('application_question_summaries', CoreBase.metadata,
    Column('id',String(36),primary_key=True),
    *[Column(name,BigInteger,nullable=False) for name in ('application_id','run_id','candidate_id','job_id')],
    Column('provider',String(64),nullable=False),Column('outcome',String(64),nullable=False),
    *[Column(name,Integer,nullable=False) for name in ('identified','answered','insufficient','rejected','schema_version')],
    Column('created_at',DateTime,nullable=False,server_default=func.now()))
