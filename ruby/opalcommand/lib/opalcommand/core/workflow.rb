# frozen_string_literal: true

module OpalCommand
  module Core
    module Workflow
      module_function

      
      GRAPH = {
        queued: %i[allocated cancelled],
        allocated: %i[departed cancelled],
        departed: %i[arrived], 
        arrived: [],
        cancelled: []
      }.freeze

      
      TERMINAL_STATES = %i[arrived cancelled].freeze 

      def transition_allowed?(src, dest)
        (GRAPH[src] || []).include?(dest)
      end

      def is_terminal_state?(state)
        TERMINAL_STATES.include?(state)
      end

      def is_valid_state?(state)
        GRAPH.key?(state)
      end

      def allowed_transitions(state)
        (GRAPH[state] || []).dup
      end

      def shortest_path(from, to)
        return [from] if from == to
        return nil unless GRAPH.key?(from) && GRAPH.key?(to)

        visited = { from => nil }
        queue = [from]

        until queue.empty?
          current = queue.shift
          (GRAPH[current] || []).each do |neighbor|
            next if visited.key?(neighbor)

            visited[neighbor] = current
            if neighbor == to
              path = [to]
              node = to
              while visited[node]
                node = visited[node]
                path.unshift(node)
              end
              return path
            end
            queue << neighbor
          end
        end
        nil
      end
    end

    TransitionRecord = Struct.new(:entity_id, :from_state, :to_state, :timestamp, keyword_init: true)

    TransitionResult = Struct.new(:success, :from_state, :to_state, :error, keyword_init: true)

    class WorkflowEngine
      def initialize
        @mutex    = Mutex.new
        @entities = {}
        @history  = []
      end

      
      def register(entity_id, initial_state: :queued)
        @mutex.synchronize do
          return false if @entities.key?(entity_id)
          

          @entities[entity_id] = initial_state
          true
        end
      end

      def get_state(entity_id)
        @mutex.synchronize { @entities[entity_id] }
      end

      
      def transition(entity_id, to_state)
        @mutex.synchronize do
          current = @entities[entity_id]
          return TransitionResult.new(success: false, error: 'entity_not_found') unless current
          

          unless Workflow.transition_allowed?(current, to_state)
            return TransitionResult.new(success: false, from_state: current, to_state: to_state, error: 'transition_not_allowed')
          end

          @entities[entity_id] = to_state
          @history << TransitionRecord.new(
            entity_id: entity_id,
            from_state: current,
            to_state: to_state,
            timestamp: Time.now.to_i
          )
          TransitionResult.new(success: true, from_state: current, to_state: to_state)
        end
      end

      
      def is_terminal?(entity_id)
        @mutex.synchronize do
          state = @entities[entity_id]
          state && Workflow.is_terminal_state?(state) 
        end
      end

      
      def active_count
        @mutex.synchronize do
          @entities.count { |_, state| !Workflow.is_terminal_state?(state) } 
        end
      end

      def history(entity_id = nil)
        @mutex.synchronize do
          if entity_id
            @history.select { |r| r.entity_id == entity_id }
          else
            @history.dup
          end
        end
      end

      def audit_log
        @mutex.synchronize do
          @history.map do |r|
            "#{r.entity_id}: #{r.from_state} -> #{r.to_state} @ #{r.timestamp}"
          end
        end
      end

      def register_at(entity_id, state)
        @mutex.synchronize do
          return false if @entities.key?(entity_id)

          @entities[entity_id] = state
          true
        end
      end

      def reopen(entity_id, to_state = :queued)
        @mutex.synchronize do
          current = @entities[entity_id]
          return TransitionResult.new(success: false, error: 'entity_not_found') unless current
          return TransitionResult.new(success: false, error: 'not_terminal') unless Workflow.is_terminal_state?(current)

          @entities[entity_id] = to_state
          @history << TransitionRecord.new(
            entity_id: entity_id,
            from_state: to_state,
            to_state: to_state,
            timestamp: Time.now.to_i
          )
          TransitionResult.new(success: true, from_state: current, to_state: to_state)
        end
      end

      def batch_transition(transitions)
        @mutex.synchronize do
          snapshot = @entities.dup
          results = []
          success_count = 0
          transitions.each do |eid, to_state|
            current = snapshot[eid]
            unless current
              results << { entity_id: eid, success: false, error: 'not_found' }
              next
            end
            unless Workflow.transition_allowed?(current, to_state)
              results << { entity_id: eid, success: false, error: 'not_allowed' }
              next
            end
            @entities[eid] = to_state
            @history << TransitionRecord.new(entity_id: eid, from_state: current, to_state: to_state, timestamp: Time.now.to_i)
            success_count += 1
            results << { entity_id: eid, success: true }
          end
          { results: results, success_count: success_count, total: transitions.length }
        end
      end

      def snapshot_and_advance(target_state)
        snapshot = @mutex.synchronize { @entities.dup }
        results = []
        snapshot.each do |entity_id, current_state|
          next if Workflow.is_terminal_state?(current_state)
          results << transition(entity_id, target_state)
        end
        results
      end

      def reconstruct_state(entity_id)
        @mutex.synchronize do
          records = @history.select { |r| r.entity_id == entity_id }
          return nil if records.empty?

          records.last.from_state
        end
      end

      def valid_transition_path?(path)
        return false if path.nil? || path.length < 2

        path.each_cons(2).all? do |src, dest|
          Workflow.transition_allowed?(src, dest)
        end
      end

      def entities_in_state(state)
        @mutex.synchronize do
          @entities.select { |_, s| s == state }.keys
        end
      end

      def transition_count(entity_id = nil)
        @mutex.synchronize do
          if entity_id
            @history.count { |r| r.entity_id == entity_id }
          else
            @history.length
          end
        end
      end
    end
  end
end
