# frozen_string_literal: true

require 'open3'
require 'json'
require 'time'
require 'set'
require 'shellwords'
require 'fileutils'

module TaskForge
  # RL Environment wrapper for TaskForge debugging environment
  class Environment
    attr_reader :work_dir, :start_time, :test_results

    # Observation space definition (Gym-compatible)
    OBSERVATION_SPACE = {
      type: 'Dict',
      spaces: {
        test_results: {
          type: 'Dict',
          keys: %w[total passed failed pass_rate passed_tests failed_tests]
        },
        reward: { type: 'Box', low: 0.0, high: 1.0, shape: [1] },
        step_count: { type: 'Discrete', n: 101 },
        action_result: { type: 'Dict' },
        bugs_remaining: { type: 'MultiBinary', n: 75 },
        bug_progress: { type: 'Dict' },
        dependency_status: { type: 'Dict' }
      }
    }.freeze

    # Action space definition (Gym-compatible)
    ACTION_SPACE = {
      type: 'Dict',
      spaces: {
        type: { type: 'Discrete', values: %w[edit read run_command run_tests] },
        file: { type: 'Text', max_length: 256 },
        content: { type: 'Text', max_length: 100_000 },
        command: { type: 'Text', max_length: 1000 }
      }
    }.freeze

    # Map source files to relevant test files for targeted testing
    FILE_TEST_MAP = {
      'app/models/user.rb'        => %w[spec/models/user_spec.rb],
      'app/models/organization.rb' => %w[spec/models/organization_spec.rb],
      'app/models/project.rb'     => %w[spec/models/project_spec.rb],
      'app/models/task.rb'        => %w[spec/models/task_spec.rb],
      'app/models/comment.rb'     => %w[spec/models/task_spec.rb],
      'app/models/notification.rb' => %w[spec/services/notification_service_spec.rb],
      'app/services/task_service.rb' => %w[spec/services/task_service_spec.rb],
      'app/services/notification_service.rb' => %w[spec/services/notification_service_spec.rb],
      'app/services/search_service.rb' => %w[spec/services/search_service_spec.rb],
      'app/services/report_service.rb' => %w[spec/services/search_service_spec.rb],
      'app/services/jwt_service.rb' => %w[spec/requests/auth_spec.rb],
      'app/controllers/api/v1/auth_controller.rb' => %w[spec/requests/auth_spec.rb],
      'app/controllers/api/v1/tasks_controller.rb' => %w[spec/models/task_spec.rb spec/services/task_service_spec.rb],
      'app/controllers/api/v1/projects_controller.rb' => %w[spec/models/project_spec.rb],
      'app/controllers/application_controller.rb' => %w[spec/requests/auth_spec.rb],
      'app/jobs/' => %w[spec/models/task_spec.rb spec/services/notification_service_spec.rb],
      'config/application.rb' => %w[spec/models/user_spec.rb spec/models/task_spec.rb spec/requests/auth_spec.rb],
      'Gemfile' => %w[spec/models/user_spec.rb]
    }.freeze

    def initialize(work_dir, max_steps: 100, timeout: 300)
      @work_dir = work_dir
      @max_steps = max_steps
      @timeout = timeout
      @test_results = {}
      @previous_pass_rate = 0.0
      @step_count = 0
      @done = false
      @truncated = false
      @previous_results = nil
      @steps_since_full_run = 0
      @full_run_interval = 3
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
      @done = false
      @truncated = false
      @previous_results = nil
      @steps_since_full_run = 0

      # Reset git state
      run_command('git checkout .')
      run_command('git clean -fd')

      # Restart Docker services
      restart_docker

      # Run migrations
      run_command('docker compose exec -T web rails db:migrate')

      # Run initial tests to get baseline
      results = run_tests
      initial_reward = calculate_reward(results)

      {
        test_results: format_test_results(results),
        reward: initial_reward,
        step_count: @step_count,
        files_changed: [],
        project_structure: get_project_structure,
        bugs_remaining: count_remaining_bugs(results),
        bug_progress: {},
        dependency_status: dependency_status(results)
      }
    end

    def step(action)
      return terminal_result if @done || @truncated

      # Validate action first
      validation_error = validate_action(action)
      if validation_error
        return build_result(
          { error: validation_error },
          @previous_results || { total: 0, passed: 0, failed: 0, pending: 0, all_passed: false },
          0.0
        )
      end

      @step_count += 1

      # Execute the action
      output = execute_action(action)

      # Determine which tests to run
      action_type = extract_action_type(action)
      if %w[edit run_command].include?(action_type)
        @steps_since_full_run += 1
        changed_file = extract_file_path(action)

        # Run targeted tests first for fast feedback
        targeted_results = changed_file ? run_targeted_tests(changed_file) : nil

        if @steps_since_full_run >= @full_run_interval || targeted_results.nil?
          results = run_tests
          @steps_since_full_run = 0
        else
          results = targeted_results
        end
      else
        results = @previous_results || run_tests
      end

      # Calculate reward
      reward = calculate_reward(results)

      # Check if done - require total > 0 for completion
      @done = results[:total].to_i > 0 && results[:all_passed] == true
      @truncated = @step_count >= @max_steps

      @previous_results = results

      build_result(output, results, reward)
    end

    # Validate an action before execution.
    # Returns nil if valid, or an error string if invalid.
    def validate_action(action)
      return 'Action must be a Hash or match EDIT:/RUN: format' unless valid_action_format?(action)

      if action.is_a?(Hash)
        action_type = action[:type] || action['type']
        return "Invalid action type: #{action_type}" unless %w[edit read run_command run_tests].include?(action_type)

        file_path = action[:file] || action['file'] || ''
        return 'File path exceeds 256 characters' if file_path.length > 256
        return 'Path traversal not allowed' if file_path.include?('..') || file_path.start_with?('/')
        full_path = File.expand_path(File.join(@work_dir, file_path))
        return 'Path escapes work directory' unless full_path.start_with?(File.expand_path(@work_dir))

        # Reject edits to test files and protected environment files
        if action_type == 'edit'
          basename = File.basename(file_path)
          if file_path.start_with?('spec/', 'test/') ||
             file_path.include?('/spec/') || file_path.include?('/test/') ||
             basename.end_with?('_spec.rb', '_test.rb') ||
             %w[spec_helper.rb rails_helper.rb].include?(basename)
            return 'Editing test files is not allowed'
          end

          # Block edits to environment/reward infrastructure
          if file_path.start_with?('environment/') ||
             file_path.include?('/environment/') ||
             file_path.start_with?('tests/') ||
             %w[Gemfile Gemfile.lock task.toml instruction.md].include?(basename) ||
             basename == 'scoring.py' || basename == 'reward.rb' || basename == 'setup.rb'
            return 'Editing environment and evaluation files is not allowed'
          end
        end

        content = action[:content] || action['content'] || ''
        return 'Content exceeds 100K character limit' if content.length > 100_000

        command = action[:command] || action['command'] || ''
        return 'Command exceeds 1000 character limit' if command.length > 1000
      end

      nil
    end

    def close
      run_command('docker compose down')
    end

    # Gymnasium-compatible step returning [obs, reward, done, truncated, info]
    def gym_step(action)
      result = step(action)
      [result[:observation], result[:reward], result[:done], result[:truncated], result[:info]]
    end

    # Get bug descriptions
    def bug_descriptions
      Reward::BUG_TEST_MAPPING.transform_values { |keywords| keywords.join(', ') }
    end

    # Get setup bugs that block initial startup
    def setup_bugs
      Reward::BUG_CATEGORIES.fetch('setup', [])
    end

    # Get success criteria
    def success_criteria
      'All 128 RSpec tests must pass to complete the challenge.'
    end

    private

    def valid_action_format?(action)
      return true if action.is_a?(Hash)
      return true if action.is_a?(String) && (action.start_with?('EDIT:') || action.start_with?('RUN:'))

      false
    end

    def extract_action_type(action)
      if action.is_a?(Hash)
        action[:type] || action['type'] || 'unknown'
      elsif action.is_a?(String)
        action.start_with?('EDIT:') ? 'edit' : 'run_command'
      else
        'unknown'
      end
    end

    def extract_file_path(action)
      if action.is_a?(Hash)
        action[:file] || action['file']
      elsif action.is_a?(String) && action.start_with?('EDIT:')
        parts = action.sub('EDIT:', '').split(':', 3)
        parts[0] if parts.size >= 1
      end
    end

    def restart_docker
      run_command('docker compose down -v')
      run_command('docker compose up -d')
      sleep 10 # Wait for services
    end

    def execute_action(action)
      if action.is_a?(String)
        return execute_legacy_action(action)
      end

      action_type = action[:type] || action['type']

      case action_type
      when 'edit'
        handle_edit_hash(action)
      when 'read'
        handle_read(action)
      when 'run_command'
        handle_run(action[:command] || action['command'] || '')
      when 'run_tests'
        { status: 'Tests will run automatically' }
      else
        { error: "Unknown action type: #{action_type}" }
      end
    end

    def execute_legacy_action(action)
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
      file_path = action[:file] || action['file']
      content = action[:content] || action['content']

      return { error: 'Missing file path' } unless file_path
      return { error: 'Missing content' } unless content

      full_path = File.expand_path(File.join(@work_dir, file_path))
      return { error: 'Path escapes work directory' } unless full_path.start_with?(File.expand_path(@work_dir))

      begin
        FileUtils.mkdir_p(File.dirname(full_path))
        File.write(full_path, content)
        { status: 'Edit applied', file: full_path }
      rescue StandardError => e
        { error: e.message }
      end
    end

    def handle_read(action)
      file_path = action[:file] || action['file']
      return { error: 'Missing file path' } unless file_path

      full_path = File.expand_path(File.join(@work_dir, file_path))
      return { error: 'Path escapes work directory' } unless full_path.start_with?(File.expand_path(@work_dir))

      begin
        content = File.read(full_path)
        { status: 'Read successful', content: content }
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

    def run_command(command)
      args = command.shellsplit
      output, status = Open3.capture2e(*args, chdir: @work_dir)
      [output, status.exitstatus]
    end

    # Run only tests relevant to a changed file for fast feedback
    def run_targeted_tests(changed_file)
      test_files = []

      FILE_TEST_MAP.each do |source_pattern, tests|
        if changed_file.start_with?(source_pattern) || changed_file == source_pattern
          test_files.concat(tests)
        end
      end

      return nil if test_files.empty?

      test_files.uniq!
      test_args = test_files.join(' ')

      output, _status = run_command(
        "docker compose exec -T web bundle exec rspec --format json #{test_args}"
      )

      begin
        parse_rspec_output(output)
      rescue JSON::ParserError
        nil
      end
    end

    def run_tests
      output, _status = run_command('docker compose exec -T web bundle exec rspec --format json')

      begin
        parse_rspec_output(output)
      rescue JSON::ParserError
        { total: 0, passed: 0, failed: 0, pending: 0, all_passed: false, output: output }
      end
    end

    def parse_rspec_output(output)
      # Find JSON in output (rspec outputs JSON at the end)
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
    end

    def calculate_reward(results)
      return 0.0 if results[:total].nil? || results[:total].zero?

      reward_calculator = Reward.new
      reward_calculator.calculate(results, @previous_pass_rate)
    end

    def format_test_results(results)
      total = results[:total] || 0
      passed = results[:passed] || 0
      failed = results[:failed] || 0

      {
        total: total,
        passed: passed,
        failed: failed,
        pass_rate: total.positive? ? (passed.to_f / total).round(4) : 0.0,
        passed_tests: [],
        failed_tests: results[:failed_examples] || []
      }
    end

    def count_remaining_bugs(results)
      return {} unless results[:failed_examples]

      remaining = {}
      reward_calc = Reward.new
      progress = reward_calc.bug_progress(results)

      progress.each do |bug_id, score|
        remaining[bug_id] = score < 1.0 # true if bug still exists
      end

      remaining
    end

    def dependency_status(results)
      return {} unless results[:failed_examples]

      reward_calc = Reward.new
      progress = reward_calc.bug_progress(results)
      status = {}

      Reward::BUG_DEPENDENCIES.each do |bug_id, deps|
        deps_met = deps.all? { |dep| (progress[dep] || 0.0) >= 1.0 }
        status[bug_id] = {
          dependencies: deps,
          dependencies_met: deps_met,
          bug_fixed: (progress[bug_id] || 0.0) >= 1.0
        }
      end

      status
    end

    def build_result(output, results, reward)
      {
        observation: {
          output: output,
          test_results: format_test_results(results),
          reward: reward,
          step_count: @step_count,
          bugs_remaining: count_remaining_bugs(results),
          dependency_status: dependency_status(results)
        },
        reward: reward,
        done: @done,
        truncated: @truncated,
        info: info
      }
    end

    def terminal_result
      {
        observation: { terminal: true },
        reward: 0.0,
        done: @done,
        truncated: @truncated,
        info: { message: 'Episode has ended' }
      }
    end

    def info
      {
        work_dir: @work_dir,
        elapsed_time: @start_time ? Time.now - @start_time : 0,
        total_bugs: 75,
        step_count: @step_count,
        max_steps: @max_steps,
        dependency_chain_depth: Reward.max_dependency_depth,
        diamond_bugs: Reward.diamond_bugs,
        cross_category_deps: Reward.cross_category_deps.size
      }
    end

    def get_project_structure
      Dir.glob(File.join(@work_dir, '**', '*.rb'))
         .reject { |f| f.include?('vendor') || f.include?('tmp') }
         .map { |f| f.sub("#{@work_dir}/", '') }
         .sort
    end
  end
end

# Entry point for standalone execution
if __FILE__ == $PROGRAM_NAME
  env = TaskForge::Environment.new(Dir.pwd)

  puts "Observation space: #{env.observation_space}"
  puts "Action space: #{env.action_space}"
  puts "Success criteria: #{env.success_criteria}"
  puts "Setup bugs: #{env.setup_bugs}"
  puts "Bug dependency depth: #{TaskForge::Reward.max_dependency_depth}"
  puts "Diamond bugs: #{TaskForge::Reward.diamond_bugs}"
  puts "Cross-category deps: #{TaskForge::Reward.cross_category_deps.size}"
  puts "Dependency coverage: #{TaskForge::Reward.dependency_coverage}%"

  obs = env.reset

  puts "\nTaskForge environment initialized"
  puts "Test Results: #{obs[:test_results]}"
  puts "Initial Reward: #{obs[:reward]}"
end
