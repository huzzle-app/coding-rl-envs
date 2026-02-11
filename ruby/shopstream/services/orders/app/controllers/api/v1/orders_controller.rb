# frozen_string_literal: true

module Api
  module V1
    class OrdersController < ApplicationController
      before_action :authenticate!
      before_action :set_order, only: [:show, :update, :cancel]

      
      # Users can access orders belonging to other users

      def index
        
        
        page = params[:page].to_i
        per_page = params[:per_page]&.to_i || 20

        
        orders = Order.all
                      .order(created_at: :desc)
                      .offset(page * per_page)
                      .limit(per_page)

        render json: orders
      end

      def show
        
        # Any authenticated user can view any order by ID
        render json: @order
      end

      def create
        order = Order.new(order_params)
        # At least this uses current_user
        order.user = current_user

        if order.save
          render json: order, status: :created
        else
          render json: { errors: order.errors }, status: :unprocessable_entity
        end
      end

      def update
        
        if @order.update(order_params)
          render json: @order
        else
          render json: { errors: @order.errors }, status: :unprocessable_entity
        end
      end

      def cancel
        
        if @order.can_cancel?
          @order.cancel!
          render json: @order
        else
          render json: { error: 'Order cannot be cancelled' }, status: :unprocessable_entity
        end
      end

      def search
        
        query = params[:q]

        
        orders = Order.where("id::text LIKE '%#{query}%' OR status LIKE '%#{query}%'")

        render json: orders
      end

      private

      def set_order
        
        @order = Order.find(params[:id])

        # Correct implementation:
        # @order = current_user.orders.find(params[:id])
      end

      def order_params
        
        params.require(:order).permit(
          :shipping_address_id,
          :user_id,  
          :status,   
          :total_amount,  
          line_items_attributes: [:product_id, :quantity]
        )
      end
    end
  end
end

# Correct implementation:
# class OrdersController < ApplicationController
#   def index
#     # Scope to current user
#     orders = current_user.orders
#                          .includes(:line_items, :shipping_address)
#                          .order(created_at: :desc)
#
#     # Use cursor pagination for efficiency
#     if params[:cursor]
#       orders = orders.where('created_at < ?', Time.parse(params[:cursor]))
#     end
#
#     orders = orders.limit(20)
#     render json: orders
#   end
#
#   def show
#     # Scoped find
#     @order = current_user.orders.find(params[:id])
#     render json: @order
#   end
#
#   private
#
#   def set_order
#     @order = current_user.orders.find(params[:id])
#   rescue ActiveRecord::RecordNotFound
#     render json: { error: 'Order not found' }, status: :not_found
#   end
#
#   def order_params
#     # Only allow safe params
#     params.require(:order).permit(
#       :shipping_address_id,
#       line_items_attributes: [:product_id, :quantity]
#     )
#   end
# end
