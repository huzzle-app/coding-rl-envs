# frozen_string_literal: true

require_relative '../test_helper'

class ResilienceTest < Minitest::Test
  def test_replay_latest_sequence_wins
    replayed = OpalCommand::Core::Resilience.replay([
                                                        { id: 'x', sequence: 1 },
                                                        { id: 'x', sequence: 4 },
                                                        { id: 'y', sequence: 2 }
                                                      ])
    assert_equal ['y:2', 'x:4'], replayed.map { |e| "#{e[:id]}:#{e[:sequence]}" }
  end
end
