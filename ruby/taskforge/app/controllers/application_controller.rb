# frozen_string_literal: true

class ApplicationController < ActionController::API
  include Pundit::Authorization

  before_action :authenticate_user!
  around_action :set_time_zone, if: :current_user

  rescue_from ActiveRecord::RecordNotFound, with: :not_found
  rescue_from ActiveRecord::RecordInvalid, with: :unprocessable_entity
  rescue_from Pundit::NotAuthorizedError, with: :forbidden

  private

  def authenticate_user!
    token = request.headers['Authorization']&.split(' ')&.last

    return render_unauthorized unless token

    begin
      payload = JwtService.decode(token)
      @current_user = User.find(payload['user_id'])
    rescue JWT::DecodeError, ActiveRecord::RecordNotFound
      render_unauthorized
    end
  end

  def current_user
    @current_user
  end

  
  def set_time_zone
    
    Time.use_zone(current_user.timezone || 'UTC') { yield }
  end

  def render_unauthorized
    render json: { error: 'Unauthorized' }, status: :unauthorized
  end

  def not_found
    render json: { error: 'Not found' }, status: :not_found
  end

  def unprocessable_entity(exception)
    render json: { error: exception.message }, status: :unprocessable_entity
  end

  def forbidden
    render json: { error: 'Forbidden' }, status: :forbidden
  end

  
  def task_params
    # Allowing all parameters without filtering
    params.require(:task).permit!
  end
end
