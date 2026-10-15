"""Append-only operational facts and lightweight question coverage.

Capture transitions inside the producer transaction, including direct SQL writers.
No historical state is invented by backfilling overwritten rows.
"""
from alembic import op
import sqlalchemy as sa
revision = '0061'
down_revision = '0060'
branch_labels = None
depends_on = None

# (table, stage, tracked columns, candidate, job, profile, application, outcome)
CONTRACTS = [
 ('billing_checkout_operations','checkout',['result','subscription_id'],'NEW.candidate_id','NULL','NULL','NULL',"IF(NEW.result IS NULL,'started','created')"),
 ('job_candidate_eligibilities','eligibility',['status','routing_score','routing_reason'], 'NEW.candidate_id','NEW.job_id','NEW.candidate_target_profile_id','NULL','NEW.status'),
 ('domain_projections','match',['data','version'],"JSON_EXTRACT(NEW.data,'$.candidate_id')","JSON_EXTRACT(NEW.data,'$.job_id')","JSON_EXTRACT(NEW.data,'$.target_profile_id')",'NULL',"JSON_UNQUOTE(JSON_EXTRACT(NEW.data,'$.status'))"),
 ('application_authorizations','authorization',['status','authorized_at','payload','application_id'],'NEW.candidate_id','NEW.job_id','NULL','NEW.application_id','NEW.status'),
 ('job_applications','application',['status','submitted_at','prepared'], '(SELECT candidate_id FROM job_matches WHERE id=NEW.job_match_id)','(SELECT job_id FROM job_matches WHERE id=NEW.job_match_id)','(SELECT candidate_target_profile_id FROM job_matches WHERE id=NEW.job_match_id)','NEW.id','NEW.status'),
 ('application_runs','attempt',['status','attempt_number','started_at','finished_at','error_message'], '(SELECT m.candidate_id FROM job_applications a JOIN job_matches m ON m.id=a.job_match_id WHERE a.id=NEW.job_application_id)','(SELECT m.job_id FROM job_applications a JOIN job_matches m ON m.id=a.job_match_id WHERE a.id=NEW.job_application_id)','NULL','NEW.job_application_id','NEW.status'),
 ('billing_payments','payment',['status','paid_at','amount','currency','failure_reason','payment_metadata'],'(SELECT candidate_id FROM billing_customers WHERE id=NEW.billing_customer_id)','NULL','NULL','NULL','NEW.status'),
 ('billing_subscriptions','subscription',['status','current_period_start','current_period_end','cancel_at','canceled_at'],'(SELECT candidate_id FROM billing_customers WHERE id=NEW.billing_customer_id)','NULL','NULL','NULL','NEW.status'),
 ('application_entitlements','access',['can_auto_apply','period_start','period_end'],'NEW.candidate_id','NULL','NULL','NULL',"IF(NEW.can_auto_apply,'active','inactive')"),
]

def upgrade():
    op.create_table('operational_facts',
      sa.Column('id',sa.BigInteger().with_variant(sa.Integer(),'sqlite'),primary_key=True,autoincrement=True),
      sa.Column('identity',sa.String(64),nullable=False,unique=True),
      sa.Column('stage',sa.String(32),nullable=False),sa.Column('source',sa.String(64),nullable=False),
      sa.Column('resource_key',sa.String(191),nullable=False),sa.Column('candidate_id',sa.BigInteger()),
      sa.Column('job_id',sa.BigInteger()),sa.Column('target_profile_id',sa.BigInteger()),
      sa.Column('application_id',sa.BigInteger()),sa.Column('outcome',sa.String(100),nullable=False),
      sa.Column('reason',sa.String(255)),sa.Column('version',sa.String(64),nullable=False),
      sa.Column('correlation_id',sa.String(255)),sa.Column('occurred_at',sa.DateTime(),nullable=False),
      sa.Column('created_at',sa.DateTime(),nullable=False,server_default=sa.func.now()),
      sa.Column('payload',sa.JSON(),nullable=False))
    for name,columns in [('stage_time',['stage','occurred_at']),('candidate_time',['candidate_id','occurred_at']),('job',['job_id']),('created',['created_at','id'])]:
        op.create_index('ix_operational_'+name,'operational_facts',columns)
    op.create_table('application_question_summaries',
      sa.Column('id',sa.String(36),primary_key=True),sa.Column('application_id',sa.BigInteger(),nullable=False),
      sa.Column('run_id',sa.BigInteger(),nullable=False),sa.Column('candidate_id',sa.BigInteger(),nullable=False),
      sa.Column('job_id',sa.BigInteger(),nullable=False),sa.Column('provider',sa.String(64),nullable=False),
      sa.Column('outcome',sa.String(64),nullable=False),sa.Column('identified',sa.Integer(),nullable=False),
      sa.Column('answered',sa.Integer(),nullable=False),sa.Column('insufficient',sa.Integer(),nullable=False),
      sa.Column('rejected',sa.Integer(),nullable=False),sa.Column('schema_version',sa.Integer(),nullable=False),
      sa.Column('created_at',sa.DateTime(),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_question_candidate_time','application_question_summaries',['candidate_id','created_at'])
    op.create_index('ix_question_run','application_question_summaries',['application_id','run_id'])
    if op.get_bind().dialect.name != 'mysql': return
    for table,stage,columns,candidate,job,profile,app,outcome in CONTRACTS:
        key=("NEW.operation_key" if table=='billing_checkout_operations' else "CONCAT(NEW.consumer,':',NEW.aggregate)" if table=='domain_projections' else "CONCAT(NEW.candidate_id,':',NEW.job_id)" if table=='application_authorizations' else 'CAST(NEW.id AS CHAR)')
        payload='NEW.data' if table=='domain_projections' else 'JSON_OBJECT('+','.join("'%s',NEW.%s"%(col,col) for col in columns)+')'
        correlation="JSON_UNQUOTE(JSON_EXTRACT(NEW.data,'$.correlation_id'))" if table=='domain_projections' else 'NULL'
        reason="JSON_UNQUOTE(JSON_EXTRACT(NEW.data,'$.status'))" if table=='domain_projections' else 'NULL'
        for action in ('INSERT','UPDATE'):
            condition="NEW.consumer='matching.decision'" if table=='domain_projections' else 'TRUE'
            if action=='UPDATE': condition+=' AND ('+' OR '.join(f'NOT (OLD.{col} <=> NEW.{col})' for col in columns)+')'
            op.execute(f'''CREATE TRIGGER bo_{stage}_{action.lower()} AFTER {action} ON {table} FOR EACH ROW
            BEGIN IF {condition} THEN
              INSERT INTO operational_facts(identity,stage,source,resource_key,candidate_id,job_id,target_profile_id,application_id,outcome,reason,version,correlation_id,occurred_at,created_at,payload)
              VALUES(UUID(),'{stage}','{table}',{key},{candidate},{job},{profile},{app},COALESCE({outcome},'unknown'),{reason},'1',{correlation},UTC_TIMESTAMP(6),UTC_TIMESTAMP(6),{payload});
            END IF; END''')
    for action in ('UPDATE','DELETE'):
        op.execute(f"CREATE TRIGGER bo_facts_no_{action.lower()} BEFORE {action} ON operational_facts FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='operational_facts is append-only'")

def downgrade():
    if op.get_bind().dialect.name=='mysql':
        for _,stage,*_rest in CONTRACTS:
            for action in ('insert','update'): op.execute(f'DROP TRIGGER IF EXISTS bo_{stage}_{action}')
        for action in ('update','delete'): op.execute(f'DROP TRIGGER IF EXISTS bo_facts_no_{action}')
    op.drop_table('application_question_summaries')
    op.drop_table('operational_facts')
