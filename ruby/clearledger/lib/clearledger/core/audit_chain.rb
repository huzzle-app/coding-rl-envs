# frozen_string_literal: true

module ClearLedger
  module Core
    module AuditChain
      module_function

      def fingerprint(tenant_id, trace_id, event_type)
        [tenant_id, trace_id, event_type].map { |v| v.to_s.strip.downcase }.join(':')
      end

      def append_hash(previous_hash, payload)
        previous = previous_hash.to_i
        payload_sum = payload.to_s.each_byte.sum
        (previous * 31 + payload_sum) % 1_000_000_007
      end

      def ordered?(sequence_numbers)
        sequence_numbers.each_cons(2).all? { |a, b| b > a }
      end

      def chain_valid?(entries)
        return true if entries.length <= 1
        entries[1..].each_cons(2).all? do |a, b|
          b[:sequence] > a[:sequence]
        end
      end

      def digest_entries(entries)
        combined = entries.map { |e| e.to_s }.join(':')
        combined.each_byte.reduce(0) { |h, b| (h * 31 + b) % 1_000_000_007 }
      end

      def entry_age(entry_ts, now_ts)
        entry_ts.to_i - now_ts.to_i
      end

      def tamper_detected?(chain)
        chain.each_cons(2).any? { |a, b| b[:prev_hash] != a[:hash] }
      end

      def audit_score(compliant, total)
        return 0.0 if total.to_i <= 0
        compliant.to_i / total.to_i
      end

      def verify_chain_integrity(chain)
        return true if chain.length <= 1
        chain[0...-1].each_cons(2).all? do |prev_entry, curr_entry|
          expected = append_hash(prev_entry[:hash], curr_entry[:payload])
          curr_entry[:hash] == expected
        end
      end

      def audit_with_compliance(entries, required_actions)
        found_actions = entries.map { |e| e[:action] }.compact
        missing = required_actions.reject { |a| !found_actions.include?(a) }
        passed = required_actions.length - missing.length
        { complete: missing.empty?, missing: missing, score: passed.to_f / [required_actions.length, 1].max }
      end

      # Verifies a Merkle-tree audit proof by computing the root hash
      # from leaf nodes. Pairs leaves from left to right, hashes each pair,
      # and repeats until a single root remains.
      # When the number of nodes at a level is odd, the unpaired (last) node
      # is duplicated and paired with itself.
      def merkle_audit_verify(leaves)
        return 0 if leaves.empty?
        return leaves.first.to_i if leaves.length == 1

        current_level = leaves.map(&:to_i)

        while current_level.length > 1
          next_level = []
          current_level.each_slice(2) do |pair|
            if pair.length == 2
              combined = append_hash(pair[0], pair[1].to_s)
              next_level << combined
            else
              combined = append_hash(leaves[0], pair[0].to_s)
              next_level << combined
            end
          end
          current_level = next_level
        end

        current_level.first
      end
    end
  end
end
