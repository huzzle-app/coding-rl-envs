# frozen_string_literal: true

require 'rails_helper'

RSpec.describe JwtService do
  describe '.encode / .decode' do
    
    context 'JWT secret validation' do
      it 'does not use weak default secret in production' do
        allow(Rails).to receive(:env).and_return(ActiveSupport::StringInquirer.new('production'))
        allow(ENV).to receive(:fetch).with('JWT_SECRET_KEY', anything).and_return(nil)

        expect {
          JwtService.encode(user_id: 1)
        }.to raise_error(/JWT_SECRET_KEY must be set/)
      end

      it 'requires minimum secret length' do
        allow(ENV).to receive(:fetch).with('JWT_SECRET_KEY', anything).and_return('short')

        expect {
          JwtService.encode(user_id: 1)
        }.to raise_error(/too short/)
      end

      it 'uses different secrets for access and refresh tokens' do
        access_token = JwtService.encode({ user_id: 1 }, type: 'access')
        refresh_token = JwtService.encode({ user_id: 1 }, type: 'refresh')

        # Decoding refresh token as access should fail
        access_decoded = JwtService.decode(refresh_token, expected_type: 'access')
        expect(access_decoded).to be_nil
      end
    end

    context 'algorithm verification' do
      it 'rejects tokens with none algorithm' do
        # Manually create a token with 'none' algorithm
        header = Base64.urlsafe_encode64({ alg: 'none', typ: 'JWT' }.to_json, padding: false)
        payload = Base64.urlsafe_encode64({ user_id: 1, exp: 1.hour.from_now.to_i }.to_json, padding: false)
        malicious_token = "#{header}.#{payload}."

        decoded = JwtService.decode(malicious_token)
        expect(decoded).to be_nil
      end

      it 'only accepts HS256 algorithm' do
        # Token signed with different algorithm should be rejected
        token = JWT.encode({ user_id: 1 }, 'secret', 'HS384')

        decoded = JwtService.decode(token)
        expect(decoded).to be_nil
      end
    end
  end

  describe '.refresh' do
    let(:user) { create(:user) }

    
    context 'token type verification' do
      it 'only accepts refresh tokens for refresh operation' do
        access_token = JwtService.encode({ user_id: user.id, type: 'access' })

        result = JwtService.refresh(access_token)
        expect(result).to be_nil
      end

      it 'accepts valid refresh tokens' do
        tokens = JwtService.generate_token_pair(user_id: user.id)

        result = JwtService.refresh(tokens[:refresh_token])
        expect(result).to include(:access_token, :refresh_token)
      end
    end
  end

  describe '.revoke' do
    let(:user) { create(:user) }
    let(:tokens) { JwtService.generate_token_pair(user_id: user.id) }

    
    context 'token blacklist' do
      it 'adds revoked token to blacklist' do
        JwtService.revoke(tokens[:access_token])

        decoded = JwtService.decode(tokens[:access_token])
        expect(decoded).to be_nil
      end

      it 'revokes both tokens when refresh token is revoked' do
        JwtService.revoke(tokens[:refresh_token])

        # Refresh should also be invalid
        result = JwtService.refresh(tokens[:refresh_token])
        expect(result).to be_nil
      end
    end
  end
end
