"""Actual ByteAsk CLI + actual Proofsmith MCP, using a scripted localhost provider.

This checks configuration, tool discovery, argument forwarding and real C++ receipts.
It deliberately does not test a model's patching ability or call any cloud provider.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from proofsmith import config
from proofsmith.gate import _copy_source, check_receipt
from proofsmith.integration import gated_run
from proofsmith.oracles.builds import snapshot_sha256


def objects(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from objects(item)
    elif isinstance(value, list):
        for item in value:
            yield from objects(item)
    elif isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            return
        if isinstance(decoded, (dict, list)):
            yield from objects(decoded)


def main():
    binary = Path(sys.argv[1]).resolve()
    example_root = Path(__file__).resolve().parents[1] / 'examples/ci-smoke'
    config.WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="byteask-transport-", dir=config.WORK) as temp:
        work = Path(temp)
        _copy_source(example_root / 'original', work / 'baseline')
        _copy_source(work / 'baseline', work / 'candidate')
        (work / 'candidate/calculation.cpp').write_text('int total(int a, int b) { return a + b; }\n')
        home = work / 'home'
        home.mkdir()
        state = {'step': 0, 'phase': 'mcp', 'tool_names': [], 'replies': [], 'error': None}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                try:
                    body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    tools = []
                    for tool in body.get('tools', []):
                        if tool.get('type') == 'namespace':
                            tools.extend(t | {'namespace': tool['name']} for t in tool.get('tools', []) if t.get('type') == 'function')
                        elif tool.get('type') == 'function':
                            tools.append(tool)
                    state['tool_names'] = [(t.get('namespace', '') + '__' + t['name']).strip('_') for t in tools]
                    replies = [v for v in objects(body.get('input', [])) if v.get('schema') == 'proofsmith.patch-gate/1' or v.get('matches') is True]
                    state['replies'].extend(replies)
                    step = state['step']
                    function_call = step < 3
                    if state['phase'] == 'patch':
                        function_call = step == 0
                        if function_call:
                            selected = next(t for t in tools if t['name'] == 'exec_command')
                            arguments = {'cmd': "printf 'int total(int a, int b) { return a + b; }\\n' > calculation.cpp",
                                         'max_output_tokens': 1000}
                    elif step == 0:
                        selected = next(t for t in tools if t['name'].endswith('seal_check'))
                        arguments = {'repo_path': str(work / 'baseline'), 'harness_path': str(example_root / 'harness'), 'oracle': 'assertion'}
                    elif step == 1:
                        sealed = next(v for v in reversed(state['replies']) if v.get('operation') == 'seal')
                        assert sealed['status'] == 'VERIFIED', sealed
                        selected = next(t for t in tools if t['name'].endswith('check_patch'))
                        arguments = {'bundle_path': sealed['bundle_path'], 'baseline_path': str(work / 'baseline'),
                                     'candidate_path': str(work / 'candidate'), 'expected_bundle_id': sealed['bundle_id']}
                    elif step == 2:
                        receipt = next(v for v in reversed(state['replies']) if v.get('operation') == 'check_patch')
                        assert receipt['status'] == 'VERIFIED', receipt
                        selected = next(t for t in tools if t['name'].endswith('evidence_check'))
                        arguments = {'evidence_path': str(Path(receipt['receipt_path']).parent)}
                    else:
                        assert any(v.get('matches') for v in state['replies'])
                    state['step'] += 1
                    events = []
                    response = {'id': f'resp_{step}', 'object': 'response', 'created_at': 1, 'status': 'in_progress', 'output': []}
                    events.append({'type': 'response.created', 'response': response})
                    if function_call:
                        item = {'type': 'function_call', 'id': f'fc_{step}', 'call_id': f'call_{step}', 'name': selected['name'],
                                'arguments': json.dumps(arguments), 'status': 'completed'}
                        if selected.get('namespace'):
                            item['namespace'] = selected['namespace']
                        events += [{'type': 'response.output_item.added', 'output_index': 0, 'item': item | {'arguments': '', 'status': 'in_progress'}},
                                   {'type': 'response.function_call_arguments.delta', 'item_id': item['id'], 'output_index': 0, 'delta': item['arguments']},
                                   {'type': 'response.function_call_arguments.done', 'item_id': item['id'], 'output_index': 0, 'arguments': item['arguments']},
                                   {'type': 'response.output_item.done', 'output_index': 0, 'item': item}]
                    else:
                        content = [{'type': 'output_text', 'text': 'SCRIPTED TRANSPORT TEST COMPLETE: supplied check qualified, paired gate VERIFIED, evidence intact.', 'annotations': []}]
                        item = {'id': 'msg_final', 'type': 'message', 'role': 'assistant', 'status': 'completed', 'content': content}
                        events.append({'type': 'response.output_item.done', 'output_index': 0, 'item': item})
                    response = response | {'status': 'completed', 'output': [item], 'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}}
                    events.append({'type': 'response.completed', 'response': response})
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.end_headers()
                    for event in events:
                        self.wfile.write(('event: ' + event['type'] + '\ndata: ' + json.dumps(event) + '\n\n').encode())
                    self.wfile.flush()
                except Exception as exc:
                    state['error'] = repr(exc)
                    self.send_error(500, str(exc))

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        quote = json.dumps
        result_root = work / 'results'
        (home / 'config.toml').write_text(f'''model = "transport-fixture"
model_provider = "fixture"
approval_policy = "never"
web_search = "disabled"
check_for_update_on_startup = false
[model_providers.fixture]
name = "Scripted localhost transport fixture"
base_url = "http://127.0.0.1:{server.server_port}/v1"
wire_api = "responses"
requires_openai_auth = false
[mcp_servers.proofsmith]
command = {quote(sys.executable)}
args = ["-m", "proofsmith.mcp_server"]
enabled = true
required = true
startup_timeout_sec = 30
tool_timeout_sec = 300
env = {{ PROOFSMITH_RESULTS_DIR = {quote(str(result_root))}, DEEPSEEK_API_KEY = "", PROOFSMITH_ALLOW_GENERATION = "0", PROOFSMITH_FAKE_LLM = "" }}
[mcp_servers.proofsmith.tools.seal_check]
approval_mode = "approve"
[mcp_servers.proofsmith.tools.check_patch]
approval_mode = "approve"
[mcp_servers.proofsmith.tools.evidence_check]
approval_mode = "approve"
''')
        env = os.environ.copy()
        env['BYTEASK_HOME'] = str(home)
        env['DEEPSEEK_API_KEY'] = ''
        env.pop('OPENAI_API_KEY', None)
        env.pop('OPENAI_BASE_URL', None)
        out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else config.RESULTS / 'integration/byteask-transport'
        out.mkdir(parents=True, exist_ok=True)
        try:
            with (out / 'byteask.jsonl').open('w') as stdout, (out / 'byteask.stderr').open('w') as stderr:
                process = subprocess.run([str(binary), 'exec', '--json', '--ephemeral', '--sandbox', 'workspace-write',
                                          '--skip-git-repo-check', '--max-turns', '8', 'Run the scripted Proofsmith transport test.'],
                                         cwd=work / 'candidate', env=env, stdout=stdout, stderr=stderr, timeout=300)
            mcp_steps = state['step']
            mcp_error = state['error']
            receipt = next((v for v in reversed(state['replies']) if v.get('operation') == 'check_patch'), None)
            sealed = next((v for v in reversed(state['replies']) if v.get('operation') == 'seal'), None)
            headless_code = None
            if process.returncode == 0 and sealed:
                state.update(phase='patch', step=0, error=None)
                original = snapshot_sha256(work / 'baseline')
                # Temporarily give only this child the fixture provider configuration.
                old_home = os.environ.get('BYTEASK_HOME')
                os.environ['BYTEASK_HOME'] = str(home)
                try:
                    headless_code = gated_run(Path(sealed['bundle_path']), 'Apply the scripted arithmetic fixture fix.',
                                             work / 'baseline', out / 'headless', sealed['bundle_id'],
                                             executable=str(binary), model='transport-fixture', timeout_s=120, max_turns=4)
                finally:
                    if old_home is None:
                        os.environ.pop('BYTEASK_HOME', None)
                    else:
                        os.environ['BYTEASK_HOME'] = old_home
                assert snapshot_sha256(work / 'baseline') == original
        finally:
            server.shutdown()
            server.server_close()
        summary = {'schema': 'proofsmith.byteask-transport/1', 'mode': 'actual ByteAsk CLI; scripted localhost provider; supplied C++ check',
                   'cloud_model_calls': 0, 'exit_code': process.returncode, 'tool_names': state['tool_names'],
                   'provider_steps': mcp_steps, 'provider_error': mcp_error, 'signed_in_model_run': False,
                   'headless_exit_code': headless_code, 'headless_provider_steps': state['step'], 'headless_provider_error': state['error'],
                   'release_tag': 'v0.1.15', 'binary_version': subprocess.check_output([str(binary), '--version'], env=env, text=True).strip()}
        if receipt:
            source = Path(receipt['receipt_path']).parent
            destination = out / 'evidence'
            if destination.exists():
                raise RuntimeError('transport evidence already exists; retain it and choose a fresh results directory')
            shutil.copytree(source, destination)
            summary['receipt'] = receipt
            summary['integrity'] = check_receipt(destination)
        (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps(summary, indent=2))
        assert process.returncode == 0 and mcp_steps == 4 and not mcp_error, summary
        assert headless_code == 0 and state['step'] == 2 and not state['error'], summary
        assert receipt and receipt['status'] == 'VERIFIED', summary
        assert not any(n.endswith('make_verifier') for n in state['tool_names']), summary


if __name__ == '__main__':
    main()
