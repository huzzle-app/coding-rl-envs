# frozen_string_literal: true

require 'open3'
require 'shellwords'
require 'fileutils'
require_relative '../lib/mercuryledger'
require_relative 'reward'

module MercuryLedger
  module Environment
    StepResult = Struct.new(:observation, :reward, :done, :info, keyword_init: true)
    TestSummary = Struct.new(:total, :passed, :failed, :pass_rate, :targeted, :output, keyword_init: true)

    class Setup
      FILE_TEST_MAP = {
        'lib/mercuryledger/core/' => ['tests/unit'],
        'migrations/' => ['tests/unit/migrations_test.rb'],
        'services/' => ['tests/services'],
        'shared/' => ['tests/services'],
        'lib/mercuryledger/' => ['tests/unit', 'tests/integration']
      }.freeze

      SAFE_COMMANDS = %w[ruby cat ls grep find head tail wc].freeze

      def initialize(work_dir)
        @work_dir = work_dir
        @max_steps = 320
        @step = 0
        @mutating_steps = 0
        @full_run_interval = 5
        @files_changed = []
        @last_test_summary = TestSummary.new(total: 0, passed: 0, failed: 0, pass_rate: 0.0, targeted: false, output: '')
      end

      def validate_path(rel)
        raise 'invalid path' if rel.nil? || rel.empty? || rel.include?('..') || rel.start_with?('/')

        abs = File.expand_path(rel, @work_dir)
        root = File.expand_path(@work_dir)
        raise 'path escapes workspace' unless abs.start_with?("#{root}/") || abs == root

        abs
      end

      def validate_action(action)
        t = action['type'] || action[:type]
        raise 'unknown action type' unless %w[edit read run_command].include?(t)

        if %w[edit read].include?(t)
          file = action['file'] || action[:file]
          validate_path(file)
          if t == 'edit'
            normalized = file.to_s.tr('\\', '/')
            is_test_path = normalized.start_with?('tests/') ||
                           normalized.include?('/tests/') ||
                           normalized.start_with?('__tests__/') ||
                           normalized.end_with?('_test.rb') ||
                           normalized.end_with?('_spec.rb')
            raise 'editing test files is not allowed' if is_test_path
          end
        end

        if t == 'run_command'
          cmd = action['command'] || action[:command]
          args = Shellwords.split(cmd.to_s)
          raise 'empty command' if args.empty?
          raise 'command not allowed' unless SAFE_COMMANDS.include?(args[0])
        end
      end

      def execute_command(command)
        args = Shellwords.split(command)
        out, status = Open3.capture2e(*args, chdir: @work_dir)
        [out, status.success?]
      end

      def edit_file(rel, content)
        abs = validate_path(rel)
        FileUtils.mkdir_p(File.dirname(abs))
        File.write(abs, content)
        @files_changed << rel
        'edit applied'
      end

      def read_file(rel)
        abs = validate_path(rel)
        File.read(abs)
      end

      def parse_minitest_summary(output, targeted)
        runs = output[/([0-9]+) runs?/, 1].to_i
        failures = output[/([0-9]+) failures?/, 1].to_i
        errors = output[/([0-9]+) errors?/, 1].to_i
        total = runs
        failed = failures + errors
        passed = [total - failed, 0].max
        pass_rate = total.positive? ? passed.to_f / total : 0.0
        TestSummary.new(total: total, passed: passed, failed: failed, pass_rate: pass_rate, targeted: targeted, output: output)
      end

      def tests_for_file(rel)
        FILE_TEST_MAP.each do |prefix, tests|
          return tests if rel.start_with?(prefix)
        end
        []
      end

      def run_targeted_tests(rel)
        targets = tests_for_file(rel)
        return TestSummary.new(total: 0, passed: 0, failed: 0, pass_rate: 0.0, targeted: true, output: '') if targets.empty?

        cmd = ['ruby', '-Ilib', '-Itests', 'tests/run_all.rb', *targets.uniq].shelljoin
        out, = execute_command(cmd)
        parse_minitest_summary(out, true)
      end

      def run_full_tests
        out, = execute_command('ruby -Ilib -Itests tests/run_all.rb')
        parse_minitest_summary(out, false)
      end

      def reset
        @step = 0
        @mutating_steps = 0
        @files_changed = []
        @last_test_summary = run_full_tests
        summary = @last_test_summary
        obs = {
          'action_result' => '',
          'step' => 0,
          'reward' => 0.0,
          'test_summary' => {
            'total' => summary.total,
            'passed' => summary.passed,
            'failed' => summary.failed,
            'pass_rate' => summary.pass_rate,
            'targeted' => summary.targeted
          }
        }
        info = {
          'step' => 0,
          'max_steps' => @max_steps,
          'total_bugs' => Reward.total_bugs,
          'target_tests' => Reward.total_tests,
          'files_changed' => [],
          'pass_rate' => summary.pass_rate,
          'tests_total' => summary.total,
          'tests_failed' => summary.failed,
          'targeted_run' => summary.targeted
        }
        StepResult.new(observation: obs, reward: 0.0, done: false, info: info)
      end

      def step(action)
        @step += 1
        begin
          validate_action(action)
        rescue StandardError => e
          return StepResult.new(
            observation: { 'action_result' => '', 'step' => @step },
            reward: 0.0,
            done: @step >= @max_steps,
            info: { 'error' => e.message, 'step' => @step }
          )
        end

        action_type = action['type'] || action[:type]
        result = ''
        had_error = nil

        begin
          case action_type
          when 'edit'
            result = edit_file(action['file'] || action[:file], action['content'] || action[:content])
          when 'read'
            result = read_file(action['file'] || action[:file])
          when 'run_command'
            result, = execute_command(action['command'] || action[:command])
          end
        rescue StandardError => e
          had_error = e.message
        end

        summary = @last_test_summary
        if %w[edit run_command].include?(action_type)
          @mutating_steps += 1
          targeted = action_type == 'edit' ? run_targeted_tests(action['file'] || action[:file]) : TestSummary.new(total: 0, passed: 0, failed: 0, pass_rate: 0.0, targeted: true, output: '')
          if targeted.total.positive? && (@mutating_steps % @full_run_interval != 0) && targeted.pass_rate < 1.0
            summary = targeted
          else
            summary = run_full_tests
          end
        end

        reward = Reward.sparse_reward(summary.pass_rate)
        @last_test_summary = summary
        done = @step >= @max_steps || (!summary.targeted && summary.total.positive? && summary.pass_rate >= 1.0)

        info = {
          'step' => @step,
          'max_steps' => @max_steps,
          'total_bugs' => Reward.total_bugs,
          'target_tests' => Reward.total_tests,
          'files_changed' => @files_changed,
          'pass_rate' => summary.pass_rate,
          'tests_total' => summary.total,
          'tests_failed' => summary.failed,
          'targeted_run' => summary.targeted
        }
        info['error'] = had_error if had_error

        obs = {
          'action_result' => result,
          'step' => @step,
          'reward' => reward,
          'test_summary' => {
            'total' => summary.total,
            'passed' => summary.passed,
            'failed' => summary.failed,
            'pass_rate' => summary.pass_rate,
            'targeted' => summary.targeted
          }
        }

        StepResult.new(observation: obs, reward: reward, done: done, info: info)
      end
    end
  end
end
