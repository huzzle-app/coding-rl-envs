# frozen_string_literal: true

require_relative '../test_helper'
require 'digest'

class SecurityTest < Minitest::Test
  def test_verify_signature_matches_digest
    payload = 'manifest:v1'
    digest = Digest::SHA256.hexdigest(payload)
    assert OpalCommand::Core::Security.verify_signature(payload, digest, digest)
    refute OpalCommand::Core::Security.verify_signature(payload, digest[0..-2], digest)
  end
end
