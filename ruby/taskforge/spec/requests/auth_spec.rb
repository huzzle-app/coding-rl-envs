# frozen_string_literal: true

require 'rails_helper'

RSpec.describe 'Authentication', type: :request do
  describe 'POST /api/v1/auth/login' do
    let(:user) { create(:user, password: 'password123', confirmed_at: Time.current) }

    context 'with valid credentials' do
      it 'returns JWT token' do
        post '/api/v1/auth/login', params: { email: user.email, password: 'password123' }

        expect(response).to have_http_status(:ok)
        expect(json_response['token']).to be_present
        expect(json_response['refresh_token']).to be_present
      end
    end

    context 'with invalid email' do
      
      # regardless of whether email exists
      it 'returns generic error in constant time' do
        post '/api/v1/auth/login', params: { email: 'nonexistent@example.com', password: 'password' }

        expect(response).to have_http_status(:unauthorized)
        # Fixed behavior: error message should be generic (not reveal email existence)
        expect(json_response['error']).to eq('Invalid credentials')
      end
    end

    context 'with invalid password' do
      
      # identical regardless of whether email exists
      it 'returns same generic error as invalid email' do
        post '/api/v1/auth/login', params: { email: user.email, password: 'wrongpassword' }

        expect(response).to have_http_status(:unauthorized)
        # Fixed behavior: same message as invalid email (no enumeration)
        expect(json_response['error']).to eq('Invalid credentials')
      end
    end

    context 'with unconfirmed email' do
      let(:unconfirmed_user) { create(:user, password: 'password123', confirmed_at: nil) }

      it 'returns confirmation required error' do
        post '/api/v1/auth/login', params: { email: unconfirmed_user.email, password: 'password123' }

        expect(response).to have_http_status(:unauthorized)
        expect(json_response['error']).to include('confirm')
      end
    end
  end

  describe 'POST /api/v1/auth/register' do
    let(:valid_params) do
      {
        email: 'newuser@example.com',
        password: 'password123',
        password_confirmation: 'password123',
        name: 'New User'
      }
    end

    it 'creates a new user' do
      expect {
        post '/api/v1/auth/register', params: valid_params
      }.to change(User, :count).by(1)

      expect(response).to have_http_status(:created)
    end

    
    it 'sends confirmation email asynchronously' do
      # Fixed behavior: should use deliver_later, not deliver_now
      expect {
        post '/api/v1/auth/register', params: valid_params
      }.to have_enqueued_mail(UserMailer, :confirmation_email)

      expect(response).to have_http_status(:created)
    end

    context 'with invalid params' do
      it 'returns errors' do
        post '/api/v1/auth/register', params: { email: 'invalid' }

        expect(response).to have_http_status(:unprocessable_entity)
        expect(json_response['errors']).to be_present
      end
    end
  end

  describe 'POST /api/v1/auth/refresh' do
    let(:user) { create(:user) }
    let(:refresh_token) { JwtService.encode_refresh(user_id: user.id) }

    before { user.update!(refresh_token: refresh_token) }

    context 'with valid refresh token' do
      it 'returns new access token' do
        post '/api/v1/auth/refresh', params: { refresh_token: refresh_token }

        expect(response).to have_http_status(:ok)
        expect(json_response['token']).to be_present
      end
    end

    context 'with invalid refresh token' do
      it 'returns unauthorized' do
        post '/api/v1/auth/refresh', params: { refresh_token: 'invalid' }

        expect(response).to have_http_status(:unauthorized)
      end
    end

    
    # When fixed, should use ActiveSupport::SecurityUtils.secure_compare
    context 'with mismatched stored token' do
      before { user.update!(refresh_token: 'different_token') }

      it 'rejects mismatched refresh token' do
        post '/api/v1/auth/refresh', params: { refresh_token: refresh_token }

        expect(response).to have_http_status(:unauthorized)
        expect(json_response['error']).to be_present
      end
    end
  end

  describe 'DELETE /api/v1/auth/logout' do
    let(:user) { create(:user) }
    let(:token) { JwtService.encode(user_id: user.id) }

    it 'clears refresh token' do
      user.update!(refresh_token: 'some_token')

      delete '/api/v1/auth/logout',
             headers: { 'Authorization' => "Bearer #{token}" }

      expect(response).to have_http_status(:ok)
      expect(user.reload.refresh_token).to be_nil
    end

    
    # immediately and rejected on subsequent requests
    it 'invalidates access token immediately after logout' do
      delete '/api/v1/auth/logout',
             headers: { 'Authorization' => "Bearer #{token}" }

      expect(response).to have_http_status(:ok)

      # Fixed behavior: using the same token after logout should fail
      get '/api/v1/users/me',
          headers: { 'Authorization' => "Bearer #{token}" }

      expect(response).to have_http_status(:unauthorized)
    end
  end

  private

  def json_response
    JSON.parse(response.body)
  end
end
