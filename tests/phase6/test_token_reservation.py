import json

from proofsmith.agent.loop import Budget, input_token_upper_bound, run_agent
from proofsmith.llm import FakeLLM, LLMResponse, ToolCall, Usage
from proofsmith.pipeline import classify


class Tools:
    terminal = None
    calls = 0
    output = "ok"

    def schemas(self):
        return []

    def dispatch(self, name, args):
        self.calls += 1
        if name == 'finish':
            self.terminal = {'tool': name, **args}
        return self.output


def reply(name='finish', usage=None, content=None):
    calls = [ToolCall('1', name, {'variant': 'plain', 'summary': 'done'})] if name else []
    return LLMResponse(content, None, calls, usage or Usage(10, 5, 0, 0), 'tool_calls')


def test_unaffordable_input_makes_no_request(tmp_path):
    llm = FakeLLM([])
    result = run_agent(llm, 'system', '界' * 10000, Tools(), Budget(50, 10000, 60), tmp_path)
    assert result.status == 'budget_exhausted' and result.steps == 0
    assert not llm.requests


def test_completion_is_reduced_to_fit_input_and_remaining_budget(tmp_path):
    llm = FakeLLM([reply()])
    result = run_agent(llm, 'system', 'user', Tools(), Budget(50, 6000, 60), tmp_path)
    request = llm.requests[0]
    bound = input_token_upper_bound(request['messages'], request['tools'])
    assert 0 < request['max_tokens'] < 16384
    assert bound + request['max_tokens'] == 6000
    assert result.status == 'finished'


def test_overrun_cannot_finish_or_call_acceptance_hook(tmp_path):
    llm = FakeLLM([reply(usage=Usage(50001, 0, 0, 0))])
    tools = Tools()
    judged = []
    result = run_agent(llm, 'system', 'user', tools, Budget(50, 50000, 60), tmp_path,
                       on_finish=lambda value: judged.append(value))
    assert result.status == 'budget_exhausted'
    assert not tools.calls and not judged


def test_growing_tool_context_stops_before_another_request(tmp_path):
    llm = FakeLLM([reply('list_dir')])
    tools = Tools()
    tools.output = 'x' * 30000
    result = run_agent(llm, 'system', 'user', tools, Budget(50, 30000, 60), tmp_path)
    assert result.status == 'budget_exhausted' and result.steps == 1
    assert len(llm.requests) == 1
    assert result.usage.prompt_tokens + result.usage.completion_tokens <= 30000


def test_classifier_reserves_input_before_first_request():
    llm = FakeLLM([])
    result = classify({'title': 't', 'body': 'b'}, 'summary', llm, Budget(2, 100, 60))
    assert not result.oracles and 'budget' in result.rationale
    assert not llm.requests


def test_classifier_retry_reserves_expanded_context():
    llm = FakeLLM([reply(None, content='x' * 30000)])
    result = classify({'title': 't', 'body': 'b'}, 'summary', llm, Budget(2, 20000, 60))
    assert not result.oracles and len(llm.requests) == 1


def test_classifier_respects_zero_steps():
    llm = FakeLLM([])
    result = classify({'title': 't'}, 'summary', llm, Budget(0, 500000, 60))
    assert not result.oracles and not llm.requests
