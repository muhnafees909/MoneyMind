"""
Advisor data-footprint reductions:
1. Profile fields are sent only when the question plausibly needs them.
2. Older conversation turns are condensed instead of replayed verbatim.
"""

from utils.financial_context import select_relevant_profile
from utils.openai_client import assemble_history, VERBATIM_HISTORY_MESSAGES

FULL_PROFILE = {
    'employment_status': 'employed',
    'annual_income': 90000,
    'marital_status': 'married',
    'dependents': 2,
    'housing_status': 'rent',
    'birth_year': 1990,
}


class TestProfileSelection:
    def test_groceries_question_sends_no_profile(self):
        _, included = select_relevant_profile(
            'what did I spend on groceries this month', FULL_PROFILE)
        assert included == []

    def test_spending_breakdown_sends_no_profile(self):
        _, included = select_relevant_profile(
            'break down my spending by category', FULL_PROFILE)
        assert included == []

    def test_emergency_fund_pulls_income_and_household(self):
        filtered, included = select_relevant_profile(
            'how big should my emergency fund be?', FULL_PROFILE)
        # sizing needs income + who depends on it + income stability
        assert 'annual_income' in included
        assert 'dependents' in included
        assert 'employment_status' in included
        # and only the relevant fields are in the filtered dict
        assert set(filtered.keys()) == set(included)

    def test_retirement_question_pulls_age_and_income(self):
        _, included = select_relevant_profile(
            'am I saving enough for retirement?', FULL_PROFILE)
        assert 'birth_year' in included
        assert 'annual_income' in included
        assert 'dependents' not in included  # not needed here

    def test_tax_question_pulls_marital_status(self):
        _, included = select_relevant_profile(
            'anything I can do to lower my taxes?', FULL_PROFILE)
        assert included == ['marital_status']

    def test_housing_question_pulls_housing(self):
        _, included = select_relevant_profile(
            'is my rent too high relative to income?', FULL_PROFILE)
        assert 'housing_status' in included

    def test_absent_fields_never_included(self):
        sparse = {'annual_income': 50000}  # only income set
        filtered, included = select_relevant_profile(
            'how big should my emergency fund be?', sparse)
        assert included == ['annual_income']
        assert filtered == {'annual_income': 50000}

    def test_no_profile_is_safe(self):
        assert select_relevant_profile('anything', None) == ({}, [])


class TestHistoryAssembly:
    def _turns(self, n):
        # n exchanges → 2n messages, user/assistant alternating
        msgs = []
        for i in range(n):
            msgs.append({'role': 'user', 'content': f'question {i}'})
            msgs.append({'role': 'assistant', 'content': f'answer {i} with $1,234 figure'})
        return msgs

    def test_short_history_kept_verbatim(self):
        h = self._turns(2)  # 4 messages ≤ 6
        out = assemble_history(h)
        assert out == [{'role': m['role'], 'content': m['content']} for m in h]

    def test_long_history_condenses_older_turns(self):
        h = self._turns(6)  # 12 messages
        out = assemble_history(h)
        # one summary note + the last VERBATIM_HISTORY_MESSAGES verbatim
        assert len(out) == 1 + VERBATIM_HISTORY_MESSAGES
        assert out[0]['role'] == 'system'
        assert 'Earlier in this conversation' in out[0]['content']
        # the most recent turns are preserved word-for-word
        assert out[-1] == {'role': 'assistant', 'content': 'answer 5 with $1,234 figure'}
        assert out[-2] == {'role': 'user', 'content': 'question 5'}

    def test_old_assistant_answers_are_dropped(self):
        h = self._turns(6)
        out = assemble_history(h)
        # the oldest answers (with their embedded figures) must not be resent
        contents = ' '.join(m['content'] for m in out)
        assert 'answer 0' not in contents
        assert 'answer 1' not in contents
        # but the older *questions* are summarized for continuity
        assert 'question 0' in out[0]['content']

    def test_none_history(self):
        assert assemble_history(None) == []
