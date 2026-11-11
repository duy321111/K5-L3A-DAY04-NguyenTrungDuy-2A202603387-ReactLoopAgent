"""Offline checks for retry limits, live cooldown and paginated observations."""
import json
import unittest
from unittest.mock import patch

from test_agent import ScriptedProvider, call, final
from agent import run_agent
from bonus.tools import BonusTools


class ReliabilityTests(unittest.TestCase):
    def test_exhausted_tool_is_removed_before_fourth_model_step(self):
        tools = BonusTools(scenario='rate_limit_always')
        provider = ScriptedProvider([
            call(str(i), 'get_vercel_status', {}) for i in range(3)
        ] + [final('Unknown Vercel status after three failed attempts')])
        result = run_agent('Check Vercel', provider, tools, 5)
        names = {s['function']['name'] for s in provider.schemas[3]}
        self.assertNotIn('get_vercel_status', names)
        self.assertIn('get_github_status', names)
        self.assertEqual(provider.histories[3][-1]['role'], 'user')
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(tools.calls[('get_vercel_status', 'vercel')], 3)

    def test_premature_final_requests_retry_then_accepts_recovered_status(self):
        tools = BonusTools(scenario='rate_limit_once')
        provider = ScriptedProvider([
            call('first', 'get_vercel_status', {}), final('Unavailable'),
            call('retry', 'get_vercel_status', {}), final('Recovered'),
        ])
        result = run_agent('Check Vercel', provider, tools, 5)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['answer'], 'Recovered')
        self.assertEqual(tools.calls[('get_vercel_status', 'vercel')], 2)
        self.assertTrue(any(e['event'] == 'validation_incomplete_evidence'
                            for e in result['trace']))

    def test_comparison_requires_details_after_status_summary(self):
        tools = BonusTools()
        incident = tools.status('vercel')['incidents'][0]['id']
        args = {'provider': 'vercel', 'incident_id': incident}
        source = tools.execute('get_incident_details', args)['url']
        provider = ScriptedProvider([
            call('status', 'get_vercel_status', {}), final('Summary only'),
            call('details', 'get_incident_details', args), final('Source: ' + source),
        ])
        result = run_agent('Compare incident scope', provider, tools, 5)
        self.assertEqual(result['status'], 'completed')
        event = next(e for e in result['trace']
                     if e['event'] == 'validation_incomplete_evidence')
        self.assertEqual(event['missing_details'], [args])

    def test_incomplete_evidence_at_budget_is_not_completed(self):
        tools = BonusTools(scenario='rate_limit_once')
        provider = ScriptedProvider([
            call('first', 'get_vercel_status', {}), final('Unavailable'),
        ])
        self.assertEqual(run_agent('Check Vercel', provider, tools, 2)['status'],
                         'max_steps')

    def test_retriable_live_cooldown_allows_honest_partial_final(self):
        tools = BonusTools(mode='live')
        provider = ScriptedProvider([
            call('first', 'get_vercel_status', {}), final('Rate limited; not verified'),
        ])
        with patch.object(tools, 'execute', return_value={
            'ok': False, 'error': 'RATE_LIMITED', 'retry_after': '120', 'retriable': True
        }) as execute, patch('agent.time.monotonic', return_value=100):
            result = run_agent('Check Vercel', provider, tools, 3)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(execute.call_count, 1)

    def test_persistent_rate_limit_stops_execution_but_other_provider_works(self):
        tools = BonusTools(scenario='rate_limit_always')
        responses = [call(str(i), 'get_vercel_status', {}) for i in range(5)]
        responses += [call('other', 'get_npm_status', {}), final('Partial results')]
        result = run_agent('Check both providers', ScriptedProvider(responses), tools, 8)
        events = [e for e in result['trace'] if e['event'] == 'tool']
        self.assertEqual(tools.calls[('get_vercel_status', 'vercel')], 3)
        self.assertEqual(events[3]['result']['error'], 'RETRY_LIMIT')
        self.assertEqual(events[-1]['result']['provider'], 'npm')
        self.assertEqual(result['status'], 'completed')

    def test_live_retry_after_defers_network_and_preserves_observation(self):
        tools = BonusTools(mode='live')
        responses = [call(str(i), 'get_vercel_status', {}) for i in range(2)]
        responses.append(final('Not verified; rate limited'))
        with patch.object(tools, 'execute', return_value={
            'ok': False, 'error': 'RATE_LIMITED', 'retry_after': '120'
        }) as execute, patch('agent.time.monotonic', return_value=100):
            provider = ScriptedProvider(responses)
            result = run_agent('Check Vercel', provider, tools, 4)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(json.loads(provider.histories[2][-1]['content'])['error'],
                         'RETRY_DEFERRED')
        self.assertEqual(result['status'], 'completed')

    def test_next_page_is_returned_with_matching_call_id(self):
        tools = BonusTools()
        incident = tools.status('vercel')['incidents'][0]['id']
        first_args = {'provider': 'vercel', 'incident_id': incident, 'offset': 0, 'limit': 1}
        first = tools.execute('get_incident_details', first_args)
        self.assertIsNotNone(first['next_offset'])
        second_args = dict(first_args, offset=first['next_offset'])
        provider = ScriptedProvider([
            call('page1', 'get_incident_details', first_args),
            call('page2', 'get_incident_details', second_args),
            final('Partial timeline. Source: ' + first['url']),
        ])
        result = run_agent('Read timeline', provider, tools, 4)
        observation = provider.histories[2][-1]
        self.assertEqual(observation['tool_call_id'], 'page2')
        self.assertEqual(json.loads(observation['content'])['offset'], first['next_offset'])
        self.assertEqual(result['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
