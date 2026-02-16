# frozen_string_literal: true

module Api
  module V1
    class UsersController < ApplicationController
      def me
        render json: UserSerializer.new(current_user).as_json
      end

      def index
        users = User.all
        render json: users.map { |u| UserSerializer.new(u).as_json }
      end

      def show
        user = User.find(params[:id])
        render json: UserSerializer.new(user).as_json
      end

      def update
        current_user.update!(user_params)
        render json: UserSerializer.new(current_user).as_json
      end

      private

      def user_params
        params.permit(:name, :username, :avatar_url, :timezone)
      end
    end
  end
end
