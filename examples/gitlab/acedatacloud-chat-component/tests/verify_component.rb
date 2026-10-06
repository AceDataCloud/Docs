require 'fileutils'
require 'json'
require 'open3'
require 'tmpdir'
require 'yaml'

def assert(value, message)
  raise message unless value
end

template = File.expand_path('../templates/commit-summary.yml', __dir__)
header, jobs = YAML.load_stream(File.read(template))
assert(header.dig('spec', 'inputs', 'model', 'default') == 'gpt-5.5', 'unexpected default model')
assert(jobs.length == 1, 'component must define one job')
job = jobs.values.first
assert(job.dig('artifacts', 'paths') == ['summary.txt'], 'artifact must contain only summary.txt')
assert(job.dig('artifacts', 'access') == 'developer', 'artifact access must be restricted')
assert(job.dig('rules', 0, 'when') == 'manual', 'billable job must be manual')
assert(job.dig('rules', 0, 'if').include?('CI_COMMIT_REF_PROTECTED'), 'job must require a protected ref')
script = job.fetch('script').join("\n")
_, syntax_error, syntax_status = Open3.capture3('sh', '-n', stdin_data: script)
assert(syntax_status.success?, "component shell syntax: #{syntax_error}")
assert(script.include?('https://api.acedata.cloud/v1/chat/completions'), 'unexpected API endpoint')

fake_curl = <<~SH
  #!/bin/sh
  set -eu
  output=''
  request=''
  authorized=false
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --output) output="$2"; shift 2 ;;
      --data-binary) request="${2#@}"; shift 2 ;;
      --header)
        if [ "$2" = "Authorization: Bearer $ACEDATACLOUD_API_TOKEN" ]; then authorized=true; fi
        shift 2 ;;
      --write-out|--connect-timeout|--max-time|--retry) shift 2 ;;
      --silent|--show-error) shift ;;
      https://api.acedata.cloud/v1/chat/completions) shift ;;
      *) exit 12 ;;
    esac
  done
  [ "$authorized" = true ] || exit 13
  cp "$request" "$FAKE_CAPTURE"
  printf '%s\n' "$request" > "$FAKE_REQUEST_PATH"
  [ "$FAKE_MODE" != transport ] || exit 7
  cp "$FAKE_RESPONSE" "$output"
  printf '%s' "$FAKE_STATUS"
SH

def run_case(script, fake_curl, response:, status: '200', mode: 'http', token: 'unit-test-token')
  Dir.mktmpdir('acedatacloud-component-') do |dir|
    bin = File.join(dir, 'bin')
    Dir.mkdir(bin)
    curl_path = File.join(bin, 'curl')
    File.write(curl_path, fake_curl)
    File.chmod(0755, curl_path)
    response_path = File.join(dir, 'fake-response.json')
    File.write(response_path, response)
    capture_path = File.join(dir, 'captured-request.json')
    request_path = File.join(dir, 'request-path.txt')
    env = {
      'PATH' => "#{bin}:#{ENV.fetch('PATH')}",
      'ACEDATACLOUD_API_TOKEN' => token,
      'ACEDATACLOUD_MODEL' => 'gpt-5.5',
      'CI_COMMIT_TITLE' => 'Fix "quotes" and \\ paths: 中文',
      'FAKE_RESPONSE' => response_path,
      'FAKE_CAPTURE' => capture_path,
      'FAKE_REQUEST_PATH' => request_path,
      'FAKE_STATUS' => status,
      'FAKE_MODE' => mode
    }
    output, error, result = Open3.capture3(env, 'sh', '-c', script, chdir: dir)
    captured = File.exist?(capture_path) ? JSON.parse(File.read(capture_path)) : nil
    summary_path = File.join(dir, 'summary.txt')
    summary = File.exist?(summary_path) ? File.read(summary_path) : nil
    if File.exist?(request_path)
      assert(!File.exist?(File.read(request_path).strip), 'temporary request was not removed')
    end
    [result.success?, output + error, captured, summary]
  end
end

ok, log, request, summary = run_case(script, fake_curl,
  response: '{"choices":[{"message":{"content":"One summary."}}]}')
assert(ok, "successful response failed: #{log}")
assert(request.fetch('model') == 'gpt-5.5', 'wrong model')
assert(request.dig('messages', 0, 'content').include?('Fix "quotes" and \\ paths: 中文'), 'title was not encoded')
assert(request.fetch('stream') == false, 'streaming must be disabled')
assert(summary == "One summary.\n", 'wrong summary artifact')
assert(!log.include?('unit-test-token'), 'token appeared in job log')

ok, log, _, summary = run_case(script, fake_curl,
  response: '{"error":"private response body"}', status: '429')
assert(!ok && log.include?('HTTP 429'), 'HTTP errors must fail with status')
assert(!log.include?('private response body') && summary.nil?, 'HTTP error body or artifact leaked')

ok, log, _, summary = run_case(script, fake_curl,
  response: '{"choices":[]}')
assert(!ok && log.include?('no text summary') && summary.nil?, 'missing summary must fail')

ok, log, _, summary = run_case(script, fake_curl,
  response: '{}', mode: 'transport')
assert(!ok && log.include?('billing outcome is unknown') && summary.nil?, 'transport failure must not retry')

ok, log, request, summary = run_case(script, fake_curl,
  response: '{}', token: nil)
assert(!ok && request.nil? && summary.nil?, 'missing token must fail before network')
assert(log.include?('ACEDATACLOUD_API_TOKEN'), 'missing token error must name the setting')

puts 'Component syntax, request encoding, artifact, error and token checks passed.'
