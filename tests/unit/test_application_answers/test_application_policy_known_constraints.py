from scaffold.application_answers.application_policy import adapt_to_constraints, deterministic, validate
from scaffold.application_answers.contracts import AnswerType, CandidateContext, Question


def test_known_salary_outside_native_bounds_is_adapted_without_rewriting_preference():
    context = CandidateContext(42, min_salary=17000, application_context={'authorized_match': True})
    question = Question('salary', 'Pretensão salarial', field_type='number', is_required=True,
                        min_value=0, max_value=15000, step_value=100)
    answer = deterministic(question, context)
    assert answer.type != AnswerType.SKIP
    assert answer.value == '15000'
    assert answer.source == 'authorized_constraint_adjustment'
    assert 'min_salary' in answer.basis
    assert context.min_salary == 17000


def test_unknown_historical_remuneration_remains_estimable_with_known_salary_preference():
    context = CandidateContext(42, min_salary=17000, application_context={'authorized_match': True})
    question = Question('history', 'Qual foi sua última remuneração recebida?', field_type='number',
                        is_required=True, min_value=0, max_value=15000, step_value=100)
    assert deterministic(question, context) is None
    answer = validate(question, {'answer': '15000', 'kind': 'estimated',
                                'basis': ['min_salary', 'application_context']}, context)
    assert answer.type != AnswerType.SKIP
    assert answer.source == 'ai_estimated'
    assert context.min_salary == 17000


def test_explicit_professional_value_adapts_to_last_valid_grid_point():
    context = CandidateContext(42, min_salary=17000, custom_answers={'salary': '20000'},
                               application_context={'authorized_match': True})
    question = Question('salary', 'Pretensão salarial', field_type='number', is_required=True,
                        min_value=1000, max_value=17550, step_value=100)
    answer = deterministic(question, context)
    assert answer.value == '17500' and answer.source == 'authorized_constraint_adjustment'
    assert 'explicit_answers' in answer.basis
    assert context.custom_answers['salary'] == '20000' and context.min_salary == 17000


def test_unique_document_value_is_never_changed_to_fit_numeric_constraints():
    context = CandidateContext(42, application_context={'authorized_match': True})
    question = Question('document', 'CPF', field_type='number', is_required=True, max_value=999)
    answer = adapt_to_constraints(question, '12345678901', context, ['explicit_answers'])
    assert answer.type == AnswerType.SKIP
