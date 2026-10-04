import pytest

from scaffold.application_answers.application_policy import validate
from scaffold.application_answers.contracts import AnswerType, CandidateContext, Question, QuestionOption


@pytest.mark.parametrize('kind', ['direct', 'derived', 'inferred'])
def test_search_filter_based_willingness_is_authorized_intent_not_explicit_candidate_fact(kind):
    context = CandidateContext(42, remote_preferences=['remote', 'hybrid', 'onsite'],
                               application_context={'authorized_match': True})
    question = Question('new-mode', 'Você tem disponibilidade para atuar em modelo híbrido?',
                        options=[QuestionOption('Não', 'no'), QuestionOption('Sim', 'yes')])
    result = validate(question, {'answer': 'yes', 'kind': kind, 'basis': ['work_mode_search_filter']}, context)
    assert result.type == AnswerType.OPTION and result.value == 'yes'
    assert result.source == 'ai_intent'
    assert set(result.basis) == {'work_mode_search_filter', 'application_context'}


@pytest.mark.parametrize('label', ['Qual foi sua última remuneração recebida?', 'Qual é seu salário atual?',
                                  'Previous compensation', 'Qual foi o último PRR recebido?'])
def test_salary_preference_anchors_estimate_but_never_proves_historical_remuneration(label):
    context = CandidateContext(42, min_salary=17000, application_context={'authorized_match': True})
    question = Question('history', label, field_type='number', is_required=True,
                        min_value=0, max_value=100000, step_value=100)
    result = validate(question, {'answer': '17000', 'kind': 'direct', 'basis': ['min_salary']}, context)
    assert result.type == AnswerType.TEXT and result.value == '17000'
    assert result.source == 'ai_estimated' and result.basis == ['min_salary']
    assert context.min_salary == 17000


def test_provenance_correction_does_not_accept_invalid_option_or_number():
    context = CandidateContext(42, min_salary=17000, remote_preferences=['hybrid'],
                               application_context={'authorized_match': True})
    question = Question('mode', 'Disponibilidade para regime híbrido?',
                        options=[QuestionOption('Sim', 'native-yes')])
    result = validate(question, {'answer': 'invented-id', 'kind': 'derived',
                                 'basis': ['work_mode_search_filter']}, context)
    assert result.type == AnswerType.SKIP
    salary = Question('pay', 'Última remuneração recebida', field_type='number', min_value=0)
    result = validate(salary, {'answer': 'NaN', 'kind': 'direct', 'basis': ['min_salary']}, context)
    assert result.type == AnswerType.SKIP
