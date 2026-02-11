# frozen_string_literal: true

module Api
  module V1
    class AuthController < ApplicationController
      skip_before_action :authenticate_user!, only: [:login, :register]

      def login
        user = User.find_by(email: params[:email]&.downcase)

        
        if user.nil?
          return render json: { error: 'Invalid credentials' }, status: :unauthorized
        end

        unless user.valid_password?(params[:password])
          
          return render json: { error: 'Invalid password' }, status: :unauthorized
        end

        unless user.confirmed?
          return render json: { error: 'Please confirm your email' }, status: :unauthorized
        end

        token = JwtService.encode(user_id: user.id)
        refresh_token = JwtService.encode_refresh(user_id: user.id)

        
        user.update!(refresh_token: refresh_token)

        render json: {
          token: token,
          refresh_token: refresh_token,
          user: UserSerializer.new(user).as_json
        }
      end

      def register
        user = User.new(register_params)

        if user.save
          
          UserMailer.confirmation_email(user).deliver_now

          render json: { message: 'Registration successful. Please check your email.' },
                 status: :created
        else
          render json: { errors: user.errors.full_messages }, status: :unprocessable_entity
        end
      end

      def logout
        
        current_user.update!(refresh_token: nil)

        render json: { message: 'Logged out successfully' }
      end

      def refresh
        refresh_token = params[:refresh_token]

        begin
          payload = JwtService.decode_refresh(refresh_token)
          user = User.find(payload['user_id'])

          
          unless user.refresh_token == refresh_token
            return render json: { error: 'Invalid refresh token' }, status: :unauthorized
          end

          new_token = JwtService.encode(user_id: user.id)

          render json: { token: new_token }
        rescue JWT::DecodeError
          render json: { error: 'Invalid refresh token' }, status: :unauthorized
        end
      end

      private

      def register_params
        params.permit(:email, :password, :password_confirmation, :name)
      end
    end
  end
end
