# frozen_string_literal: true

class ReservationService
  
  # Two concurrent requests can both succeed even if only enough stock for one

  def initialize(product_id)
    @product_id = product_id
    @product = Product.find(product_id)
  end

  def reserve(quantity, order_id:, expires_in: 15.minutes)
    
    # Thread 1: checks stock = 10, wants 8
    # Thread 2: checks stock = 10, wants 5
    # Both see enough stock and proceed
    # Thread 1: reserves 8, stock = 2
    # Thread 2: reserves 5, but stock is only 2 (oversold!)

    return failure('Insufficient stock') if @product.stock < quantity

    
    reservation = StockReservation.create!(
      product_id: @product_id,
      order_id: order_id,
      quantity: quantity,
      expires_at: Time.current + expires_in
    )

    
    @product.stock -= quantity
    @product.save!

    success(reservation)
  rescue ActiveRecord::RecordNotUnique
    failure('Already reserved')
  end

  def release(reservation_id)
    reservation = StockReservation.find(reservation_id)

    @product.stock += reservation.quantity
    @product.save!

    reservation.destroy!
    success
  end

  def commit(reservation_id)
    reservation = StockReservation.find(reservation_id)
    reservation.update!(status: 'committed')
    success
  end

  private

  def success(data = nil)
    { success: true, data: data }
  end

  def failure(error)
    { success: false, error: error }
  end
end

# Correct implementation using pessimistic locking:
# def reserve(quantity, order_id:, expires_in: 15.minutes)
#   Product.transaction do
#     product = Product.lock.find(@product_id)
#
#     if product.stock < quantity
#       return failure('Insufficient stock')
#     end
#
#     product.decrement!(:stock, quantity)
#
#     reservation = StockReservation.create!(
#       product_id: @product_id,
#       order_id: order_id,
#       quantity: quantity,
#       expires_at: Time.current + expires_in
#     )
#
#     success(reservation)
#   end
# end
#
# Or using optimistic locking with retry:
# def reserve(quantity, order_id:, expires_in: 15.minutes)
#   retries = 0
#   begin
#     Product.transaction do
#       product = Product.find(@product_id)
#       return failure('Insufficient stock') if product.stock < quantity
#
#       # This uses lock_version and raises StaleObjectError on conflict
#       product.decrement!(:stock, quantity)
#       # ... create reservation
#     end
#   rescue ActiveRecord::StaleObjectError
#     retries += 1
#     retry if retries < 3
#     failure('Concurrent modification, please retry')
#   end
# end
