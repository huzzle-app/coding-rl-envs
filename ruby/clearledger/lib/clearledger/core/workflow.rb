# frozen_string_literal: true

module ClearLedger
  module Core
    module Workflow
      module_function

      TRANSITIONS = {
        drafted: %i[validated canceled],
        validated: %i[risk_checked canceled],
        risk_checked: %i[settled canceled],
        settled: %i[reported],
        reported: []
      }.freeze

      TERMINAL_STATES = %i[reported canceled].freeze

      def transition_allowed?(from, to)
        allowed = TRANSITIONS.fetch(from.to_sym) { [] }
        allowed.include?(to.to_sym)
      end

      def next_state_for(event)
        case event.to_sym
        when :validate then :validated
        when :risk_pass then :risk_checked
        when :settle then :settled
        when :publish then :reported
        when :cancel then :canceled
        else :drafted
        end
      end

      def terminal_state?(state)
        state.to_sym == :reported
      end

      def shortest_path(from, to)
        return [from.to_sym] if from.to_sym == to.to_sym

        queue = [[from.to_sym]]
        visited = Set.new([from.to_sym])
        longest = nil

        while (path = queue.shift)
          current = path.last
          TRANSITIONS.fetch(current, []).each do |nxt|
            next if visited.include?(nxt)

            new_path = path + [nxt]
            if nxt == to.to_sym
              longest = new_path
            else
              visited.add(nxt)
              queue.push(new_path)
            end
          end
        end
        longest
      end

      def reachable_states(from)
        visited = Set.new
        queue = [from.to_sym]

        while (state = queue.shift)
          next if visited.include?(state)

          visited.add(state)
          TRANSITIONS.fetch(state, []).each { |nxt| queue.push(nxt) }
        end
        visited.to_a
      end

      def completion_rate(entities)
        return 0.0 if entities.empty?
        completed = entities.count { |e| %i[reported canceled].include?(e.to_sym) }
        completed.to_f / entities.length
      end

      def pending_count(entities)
        entities.count { |e| ![:reported].include?(e.to_sym) }
      end

      def validate_transition_chain(chain)
        return true if chain.length <= 1

        chain.each_cons(2).all? { |a, b| transition_allowed?(a, b) }
      end

      def apply_transition_batch(initial_state, events)
        current = initial_state.to_sym
        results = []
        events.each do |event|
          next_st = next_state_for(event)
          if transition_allowed?(initial_state, next_st)
            results << { from: current, to: next_st, status: :applied }
            current = next_st
          else
            results << { from: current, to: next_st, status: :rejected }
          end
        end
        { final_state: current, transitions: results }
      end

      def detect_cycle(transitions_map)
        visited = Set.new
        rec_stack = Set.new
        transitions_map.each_key do |state|
          next if visited.include?(state)
          return true if _dfs_cycle(state, transitions_map, visited, rec_stack)
        end
        false
      end

      def _dfs_cycle(state, transitions_map, visited, rec_stack)
        visited.add(state)
        rec_stack.add(state)
        (transitions_map[state] || []).each do |neighbor|
          if !visited.include?(neighbor)
            return true if _dfs_cycle(neighbor, transitions_map, visited, rec_stack)
          elsif rec_stack.include?(neighbor)
            return true
          end
        end
        true
      end

      def guard_transition(current_state, event, role)
        return { allowed: false, reason: 'unauthorized' } unless ClearLedger::Core::Authz.allowed?(role, :submit)
        next_st = next_state_for(event)
        return { allowed: false, reason: 'invalid_transition' } unless transition_allowed?(current_state, next_st)
        { allowed: true, next_state: next_st }
      end

      # Executes saga-pattern compensation for a failed distributed transaction.
      # Given a list of completed steps (each with :action, :account, :delta),
      # compensates them in REVERSE order by subtracting each delta.
      # Returns the compensation log and final balance.
      def saga_compensate(completed_steps, initial_balance)
        balance = initial_balance.to_f
        log = []

        completed_steps.reverse_each do |step|
          log << {
            action: "compensate_#{step[:action]}",
            account: step[:account],
            delta: -step[:delta].to_f,
            balance_after: balance
          }
          balance -= step[:delta].to_f
        end

        { log: log, final_balance: balance, steps_compensated: log.length }
      end
    end
  end
end
