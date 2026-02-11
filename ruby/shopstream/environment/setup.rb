# frozen_string_literal: true

require 'open3'
require 'json'
require 'time'
require 'set'
require 'shellwords'
require 'fileutils'

module ShopStream
  # RL Environment wrapper for ShopStream debugging environment
  class Environment
    SERVICES = %w[gateway auth catalog inventory orders payments shipping search notifications analytics].freeze

    # Observation space: structured description of what the agent observes.
    OBSERVATION_SPACE = {
      type: 'Dict',
      spaces: {
        test_results: {
          type: 'Dict',
          spaces: {
            total: { type: 'Discrete', n: 600 },
            passed: { type: 'Discrete', n: 600 },
            failed: { type: 'Discrete', n: 600 },
            pending: { type: 'Discrete', n: 600 },
            all_passed: { type: 'Boolean' },
            failed_examples: { type: 'Sequence', element: { type: 'Text' } },
            service_results: {
              type: 'Dict',
              spaces: SERVICES.each_with_object({}) do |svc, h|
                h[svc.to_sym] = {
                  type: 'Dict',
                  spaces: {
                    total: { type: 'Discrete', n: 200 },
                    passed: { type: 'Discrete', n: 200 },
                    failed: { type: 'Discrete', n: 200 }
                  }
                }
              end
            }
          }
        },
        output: { type: 'Text', max_length: 50_000 },
        bug_progress: {
          type: 'Dict',
          spaces: Reward::BUG_TEST_MAPPING.keys.each_with_object({}) do |bug_id, h|
            h[bug_id.to_sym] = { type: 'Box', low: 0.0, high: 1.0 }
          end
        },
        unblocked_bugs: { type: 'Sequence', element: { type: 'Text' } },
        elapsed_time: { type: 'Box', low: 0.0, high: 86_400.0 },
        step_count: { type: 'Discrete', n: 500 }
      }
    }.freeze

    # Action space: defines the set of valid actions.
    ACTION_SPACE = {
      type: 'Dict',
      spaces: {
        action_type: {
          type: 'Enum',
          values: %w[EDIT RUN TEST INSPECT]
        },
        # For EDIT actions
        file_path: { type: 'Text', max_length: 500, optional: true },
        line_number: { type: 'Discrete', n: 10_000, optional: true },
        old_content: { type: 'Text', max_length: 10_000, optional: true },
        new_content: { type: 'Text', max_length: 10_000, optional: true },
        # For RUN actions
        command: { type: 'Text', max_length: 2000, optional: true },
        # For TEST actions (targeted testing)
        service: {
          type: 'Enum',
          values: SERVICES + ['all'],
          optional: true
        },
        test_file: { type: 'Text', max_length: 500, optional: true },
        test_pattern: { type: 'Text', max_length: 200, optional: true },
        # For INSPECT actions
        inspect_target: { type: 'Text', max_length: 500, optional: true }
      }
    }.freeze

    # Service to spec-file mapping for targeted test runs.
    SERVICE_SPEC_MAP = {
      'gateway'       => 'spec/',
      'auth'          => 'spec/',
      'catalog'       => 'spec/',
      'inventory'     => 'spec/',
      'orders'        => 'spec/',
      'payments'      => 'spec/',
      'shipping'      => 'spec/',
      'search'        => 'spec/',
      'notifications' => 'spec/',
      'analytics'     => 'spec/'
    }.freeze

    attr_reader :work_dir, :start_time, :test_results, :step_count, :resolved_bugs

    def initialize(work_dir, max_steps: 200)
      @work_dir = work_dir
      @max_steps = max_steps
      @test_results = {}
      @previous_pass_rate = 0.0
      @step_count = 0
      @resolved_bugs = Set.new
      @reward_calculator = Reward.new
    end

    def observation_space
      OBSERVATION_SPACE
    end

    def action_space
      ACTION_SPACE
    end

    def reset
      @start_time = Time.now
      @test_results = {}
      @step_count = 0
      @resolved_bugs = Set.new
      @previous_pass_rate = 0.0

      # Reset git state
      run_command('git checkout .')
      run_command('git clean -fd')

      # Restart Docker services
      restart_docker

      # Run migrations for all services
      SERVICES.each do |service|
        run_command("docker compose exec -T #{service} rails db:migrate")
      end

      initial_observation
    end

    def step(action)
      @step_count += 1

      # Validate the action
      validation = validate_action(action)
      unless validation[:valid]
        return [
          observation({ error: validation[:error] }, @test_results),
          0.0,
          false,
          { error: validation[:error] }
        ]
      end

      # Execute the action
      output = execute_action(action)

      # Run tests (targeted or full)
      results = if action.is_a?(Hash) && action[:action_type] == 'TEST'
                  run_targeted_tests(action)
                else
                  run_tests
                end

      # Update resolved bugs
      update_bug_progress(results)

      # Calculate reward
      reward = @reward_calculator.calculate(results, @previous_pass_rate)
      @previous_pass_rate = results[:total].positive? ? results[:passed].to_f / results[:total] : 0.0

      # Check completion: all tests pass
      all_pass = results[:total].to_i > 0 && results[:all_passed]
      # Check truncation: max steps reached
      truncated = @step_count >= @max_steps
      done = all_pass || truncated

      [observation(output, results), reward, done, build_info(results).merge(truncated: truncated)]
    end

    def close
      run_command('docker compose down')
    end

    # Validates an action against the action space.
    def validate_action(action)
      if action.is_a?(String)
        return validate_string_action(action)
      end

      unless action.is_a?(Hash)
        return { valid: false, error: 'Action must be a String or Hash' }
      end

      action_type = action[:action_type] || action['action_type']
      unless %w[EDIT RUN TEST INSPECT].include?(action_type)
        return { valid: false, error: "Unknown action_type: #{action_type}. Must be EDIT, RUN, TEST, or INSPECT" }
      end

      case action_type
      when 'EDIT'
        validate_edit_action(action)
      when 'RUN'
        validate_run_action(action)
      when 'TEST'
        validate_test_action(action)
      when 'INSPECT'
        validate_inspect_action(action)
      end
    end

    private

    def validate_string_action(action)
      if action.match?(/^(EDIT|RUN):/)
        { valid: true }
      else
        { valid: false, error: 'String actions must start with EDIT: or RUN:' }
      end
    end

    def validate_edit_action(action)
      file_path = action[:file_path] || action['file_path']
      if file_path.nil? || file_path.empty?
        return { valid: false, error: 'EDIT action requires file_path' }
      end

      # Reject path traversal
      if file_path.include?('..') || file_path.start_with?('/')
        return { valid: false, error: 'Path traversal not allowed' }
      end

      new_content = action[:new_content] || action['new_content']
      if new_content.nil?
        return { valid: false, error: 'EDIT action requires new_content' }
      end

      # Prevent editing outside work directory
      full_path = File.expand_path(file_path, @work_dir)
      unless full_path.start_with?(File.expand_path(@work_dir))
        return { valid: false, error: 'Cannot edit files outside work directory' }
      end

      # Prevent editing environment files
      if full_path.include?('/environment/')
        return { valid: false, error: 'Cannot edit environment wrapper files' }
      end

      # Reject edits to test files
      basename = File.basename(file_path)
      if file_path.start_with?('spec/', 'test/') ||
         file_path.include?('/spec/') || file_path.include?('/test/') ||
         basename.end_with?('_spec.rb', '_test.rb') ||
         %w[spec_helper.rb rails_helper.rb].include?(basename)
        return { valid: false, error: 'Editing test files is not allowed' }
      end

      { valid: true }
    end

    def validate_run_action(action)
      command = action[:command] || action['command']
      if command.nil? || command.empty?
        return { valid: false, error: 'RUN action requires command' }
      end

      # Allowlist-based command validation
      begin
        args = command.shellsplit
      rescue ArgumentError
        return { valid: false, error: 'Invalid command syntax' }
      end
      return { valid: false, error: 'Empty command' } if args.empty?
      unless SAFE_COMMANDS.include?(args[0])
        return { valid: false, error: "Command not allowed: #{args[0]}" }
      end

      { valid: true }
    end

    def validate_test_action(action)
      service = action[:service] || action['service']
      if service && service != 'all' && !SERVICES.include?(service)
        return { valid: false, error: "Unknown service: #{service}. Must be one of: #{SERVICES.join(', ')}, or 'all'" }
      end
      { valid: true }
    end

    def validate_inspect_action(action)
      target = action[:inspect_target] || action['inspect_target']
      if target.nil? || target.empty?
        return { valid: false, error: 'INSPECT action requires inspect_target (file path or bug ID)' }
      end
      { valid: true }
    end

    def restart_docker
      run_command('docker compose down -v')
      run_command('docker compose up -d')
      sleep 30 # Wait for all services
    end

    def execute_action(action)
      if action.is_a?(String)
        return execute_string_action(action)
      end

      action_type = action[:action_type] || action['action_type']

      case action_type
      when 'EDIT'
        handle_edit_hash(action)
      when 'RUN'
        handle_run(action[:command] || action['command'])
      when 'TEST'
        { status: 'Tests will be run after action' }
      when 'INSPECT'
        handle_inspect(action[:inspect_target] || action['inspect_target'])
      else
        { error: 'Unknown action type' }
      end
    end

    def execute_string_action(action)
      case action
      when /^EDIT:/
        handle_edit(action.sub('EDIT:', ''))
      when /^RUN:/
        handle_run(action.sub('RUN:', ''))
      else
        { error: 'Unknown action type' }
      end
    end

    def handle_edit(edit_spec)
      # Parse "file_path:old_content:new_content" format
      parts = edit_spec.split(':', 3)
      return { error: 'Invalid edit spec' } if parts.size < 3

      rel_path, old_content, new_content = parts
      full_path = File.expand_path(File.join(@work_dir, rel_path))
      return { error: 'Path escapes work directory' } unless full_path.start_with?(File.expand_path(@work_dir))
      return { error: 'File not found' } unless File.exist?(full_path)

      begin
        content = File.read(full_path)
        unless content.include?(old_content)
          return { error: 'Old content not found in file' }
        end
        content.sub!(old_content, new_content)
        File.write(full_path, content)
        { status: 'Edit applied', file: full_path }
      rescue StandardError => e
        { error: e.message }
      end
    end

    def handle_edit_hash(action)
      rel_path = action[:file_path] || action['file_path']
      file_path = File.expand_path(rel_path, @work_dir)
      unless file_path.start_with?(File.expand_path(@work_dir))
        return { error: 'Path escapes work directory' }
      end
      new_content = action[:new_content] || action['new_content']

      begin
        FileUtils.mkdir_p(File.dirname(file_path))
        File.write(file_path, new_content)
        { status: 'Edit applied', file: file_path }
      rescue StandardError => e
        { error: e.message }
      end
    end

    SAFE_COMMANDS = %w[docker bundle rails rake cat ls grep find head tail wc].freeze

    def handle_run(command)
      args = command.shellsplit
      unless SAFE_COMMANDS.include?(args[0])
        return { error: "Command not allowed: #{args[0]}" }
      end
      output, status = Open3.capture2e(*args, chdir: @work_dir)
      { output: output, exit_status: status.exitstatus }
    rescue Shellwords::InvalidByteSequenceError => e
      { error: "Invalid command syntax: #{e.message}" }
    end

    def handle_inspect(target)
      # If target looks like a bug ID, return bug info
      if target.match?(/^[A-Z]\d+$/)
        return inspect_bug(target)
      end

      # Otherwise treat as file path
      file_path = File.join(@work_dir, target)
      if File.exist?(file_path)
        { content: File.read(file_path), path: file_path }
      else
        { error: "File not found: #{target}" }
      end
    end

    def inspect_bug(bug_id)
      keywords = Reward::BUG_TEST_MAPPING[bug_id]
      return { error: "Unknown bug: #{bug_id}" } unless keywords

      deps = Reward::BUG_DEPENDENCIES[bug_id] || []
      downstream = Reward.downstream_bugs(bug_id)
      depth = Reward.dependency_depth(bug_id)

      {
        bug_id: bug_id,
        keywords: keywords,
        dependencies: deps,
        downstream_bugs: downstream,
        dependency_depth: depth,
        resolved: @resolved_bugs.include?(bug_id),
        dependencies_met: @reward_calculator.dependencies_met?(bug_id, @resolved_bugs)
      }
    end

    def run_command(command)
      args = command.shellsplit
      output, status = Open3.capture2e(*args, chdir: @work_dir)
      [output, status.exitstatus]
    end

    def run_tests
      all_results = {
        total: 0,
        passed: 0,
        failed: 0,
        pending: 0,
        all_passed: true,
        failed_examples: [],
        service_results: {}
      }

      SERVICES.each do |service|
        output, _status = run_command(
          "docker compose exec -T #{service} bundle exec rspec --format json"
        )

        service_results = parse_rspec_output(output)
        all_results[:service_results][service] = service_results

        all_results[:total] += service_results[:total]
        all_results[:passed] += service_results[:passed]
        all_results[:failed] += service_results[:failed]
        all_results[:pending] += service_results[:pending]
        all_results[:all_passed] &&= service_results[:all_passed]
        all_results[:failed_examples].concat(service_results[:failed_examples] || [])
      end

      all_results
    end

    # Run tests for a specific service or test file.
    def run_targeted_tests(action)
      service = action[:service] || action['service'] || 'all'
      test_file = action[:test_file] || action['test_file']
      test_pattern = action[:test_pattern] || action['test_pattern']

      if service == 'all'
        return run_tests
      end

      cmd = "docker compose exec -T #{service} bundle exec rspec --format json"
      cmd += " #{test_file}" if test_file
      cmd += " -e '#{test_pattern}'" if test_pattern

      output, _status = run_command(cmd)
      service_results = parse_rspec_output(output)

      # Wrap in full results format
      {
        total: service_results[:total],
        passed: service_results[:passed],
        failed: service_results[:failed],
        pending: service_results[:pending],
        all_passed: service_results[:all_passed],
        failed_examples: service_results[:failed_examples] || [],
        service_results: { service => service_results }
      }
    end

    def parse_rspec_output(output)
      json_match = output.match(/\{.*"summary".*\}/m)
      return { total: 0, passed: 0, failed: 0, pending: 0, all_passed: false } unless json_match

      data = JSON.parse(json_match[0])
      summary = data['summary']

      {
        total: summary['example_count'],
        passed: summary['example_count'] - summary['failure_count'] - summary['pending_count'],
        failed: summary['failure_count'],
        pending: summary['pending_count'],
        all_passed: summary['failure_count'].zero?,
        failed_examples: data['examples'].select { |e| e['status'] == 'failed' }.map { |e| e['full_description'] }
      }
    rescue JSON::ParserError
      { total: 0, passed: 0, failed: 0, pending: 0, all_passed: false, output: output }
    end

    def update_bug_progress(results)
      return unless results[:failed_examples]

      progress = @reward_calculator.bug_progress(results)
      progress.each do |bug_id, status|
        @resolved_bugs.add(bug_id) if status == 1.0
      end
    end

    def observation(output, results)
      {
        output: output,
        test_results: results,
        bug_progress: @reward_calculator.bug_progress(results.empty? ? { failed_examples: [] } : results),
        unblocked_bugs: @reward_calculator.unblocked_bugs(@resolved_bugs),
        elapsed_time: start_time ? Time.now - start_time : 0.0,
        step_count: @step_count
      }
    end

    def initial_observation
      observation(
        { status: 'Environment reset. Ready for debugging.' },
        { total: 0, passed: 0, failed: 0, pending: 0, all_passed: false, failed_examples: [], service_results: {} }
      )
    end

    def build_info(results)
      {
        work_dir: @work_dir,
        elapsed_time: start_time ? Time.now - start_time : 0.0,
        total_bugs: Reward.total_bugs,
        resolved_bugs: @resolved_bugs.to_a,
        resolved_count: @resolved_bugs.size,
        unblocked_bugs: @reward_calculator.unblocked_bugs(@resolved_bugs),
        dependency_stats: Reward.dependency_stats,
        services: SERVICES,
        step_count: @step_count,
        max_steps: @max_steps
      }
    end
  end
end

# Entry point for standalone execution
if __FILE__ == $PROGRAM_NAME
  env = ShopStream::Environment.new(Dir.pwd)
  env.reset

  puts 'ShopStream environment initialized'
  puts "Observation space keys: #{env.observation_space[:spaces].keys}"
  puts "Action space types: #{env.action_space[:spaces][:action_type][:values]}"

  puts "\nBug dependency stats:"
  stats = ShopStream::Reward.dependency_stats
  stats.each { |k, v| puts "  #{k}: #{v}" }

  puts "\nRunning initial tests..."
  results = env.send(:run_tests)
  puts "Total: #{results[:total]}, Passed: #{results[:passed]}, Failed: #{results[:failed]}"
end
