# ShopStream - Greenfield Development Tasks

These tasks require implementing **new modules from scratch** within the ShopStream e-commerce platform. Each task must follow existing architectural patterns, integrate with the microservices ecosystem, and pass comprehensive tests.

**Test Command:** `bundle exec rspec`

---

## Task 1: Product Recommendation Engine

### Overview

Implement a recommendation service that provides personalized product suggestions based on user behavior, purchase history, and product relationships.

### Location

Create the service in: `services/recommendations/`

### Interface Contract

```ruby
# frozen_string_literal: true

module ShopStream
  module Recommendations
    # Generates personalized product recommendations for users
    #
    # @example Basic usage
    #   engine = RecommendationEngine.new(user_id: 'user_123')
    #   recommendations = engine.get_recommendations(limit: 10)
    #
    class RecommendationEngine
      # Initialize the recommendation engine for a specific user
      #
      # @param user_id [String] The unique identifier of the user
      # @param redis [Redis] Optional Redis client for caching
      # @raise [ArgumentError] if user_id is blank
      def initialize(user_id:, redis: nil)
      end

      # Get personalized product recommendations
      #
      # @param limit [Integer] Maximum number of recommendations (default: 10)
      # @param strategy [Symbol] Recommendation strategy (:collaborative, :content_based, :hybrid)
      # @param exclude_purchased [Boolean] Exclude previously purchased products (default: true)
      # @return [Array<RecommendationResult>] Ordered list of recommendations with scores
      def get_recommendations(limit: 10, strategy: :hybrid, exclude_purchased: true)
      end

      # Get products frequently bought together with a given product
      #
      # @param product_id [String] The product to find companions for
      # @param limit [Integer] Maximum number of results (default: 5)
      # @return [Array<RecommendationResult>] Products frequently purchased together
      def frequently_bought_together(product_id:, limit: 5)
      end

      # Get similar products based on attributes and categories
      #
      # @param product_id [String] The reference product
      # @param limit [Integer] Maximum number of results (default: 10)
      # @return [Array<RecommendationResult>] Similar products ranked by similarity score
      def similar_products(product_id:, limit: 10)
      end

      # Record user interaction for improving recommendations
      #
      # @param product_id [String] The product interacted with
      # @param interaction_type [Symbol] Type of interaction (:view, :cart_add, :purchase, :wishlist)
      # @param metadata [Hash] Additional interaction data
      # @return [Boolean] Whether the interaction was recorded successfully
      def record_interaction(product_id:, interaction_type:, metadata: {})
      end

      # Invalidate cached recommendations for the user
      #
      # @return [Boolean] Whether cache was cleared
      def invalidate_cache!
      end
    end

    # Represents a single recommendation result
    #
    # @attr_reader product_id [String] The recommended product ID
    # @attr_reader score [Float] Recommendation confidence score (0.0-1.0)
    # @attr_reader reason [Symbol] Why this product was recommended
    # @attr_reader metadata [Hash] Additional recommendation context
    class RecommendationResult
      attr_reader :product_id, :score, :reason, :metadata

      def initialize(product_id:, score:, reason:, metadata: {})
      end

      def to_h
      end
    end

    # Processes user behavior events for recommendation model updates
    class BehaviorProcessor
      # Process a batch of user behavior events
      #
      # @param events [Array<Hash>] Behavior events to process
      # @return [Integer] Number of events successfully processed
      def process_events(events)
      end

      # Build co-occurrence matrix for collaborative filtering
      #
      # @param time_window [Integer] Hours of data to consider (default: 720 = 30 days)
      # @return [Hash] Co-occurrence data structure
      def build_cooccurrence_matrix(time_window: 720)
      end
    end
  end
end
```

### Required Models

```ruby
# services/recommendations/app/models/user_interaction.rb
class UserInteraction < ApplicationRecord
  # Columns: user_id, product_id, interaction_type, weight, metadata (jsonb), created_at
  belongs_to :user
  belongs_to :product

  validates :interaction_type, inclusion: { in: %w[view cart_add purchase wishlist] }

  scope :recent, ->(hours) { where('created_at > ?', hours.hours.ago) }
  scope :by_type, ->(type) { where(interaction_type: type) }
end

# services/recommendations/app/models/product_similarity.rb
class ProductSimilarity < ApplicationRecord
  # Columns: product_id, similar_product_id, similarity_score, similarity_type, updated_at
  belongs_to :product
  belongs_to :similar_product, class_name: 'Product'

  validates :similarity_score, numericality: { in: 0.0..1.0 }

  scope :by_type, ->(type) { where(similarity_type: type) }
  scope :above_threshold, ->(min) { where('similarity_score >= ?', min) }
end

# services/recommendations/app/models/recommendation_cache.rb
class RecommendationCache < ApplicationRecord
  # Columns: user_id, recommendations (jsonb), strategy, expires_at, created_at
  validates :user_id, presence: true, uniqueness: { scope: :strategy }

  scope :valid, -> { where('expires_at > ?', Time.current) }
end
```

### Required Background Jobs

```ruby
# services/recommendations/app/jobs/similarity_calculation_job.rb
class SimilarityCalculationJob < ApplicationJob
  queue_as :recommendations

  # Recalculate product similarity scores
  def perform(product_id = nil)
  end
end

# services/recommendations/app/jobs/cooccurrence_update_job.rb
class CooccurrenceUpdateJob < ApplicationJob
  queue_as :recommendations

  # Update co-occurrence matrix from recent purchases
  def perform(time_window_hours: 720)
  end
end
```

### Kafka Event Integration

Subscribe to these events from other services:
- `order.completed` - Record purchase interactions
- `product.viewed` - Record view interactions
- `cart.item_added` - Record cart interactions
- `wishlist.item_added` - Record wishlist interactions

Publish these events:
- `recommendations.generated` - When recommendations are computed
- `recommendations.clicked` - When user clicks a recommendation

### Acceptance Criteria

1. **Unit Tests (40+ specs)**
   - RecommendationEngine initialization and configuration
   - Each recommendation strategy (collaborative, content-based, hybrid)
   - Interaction recording with all types
   - Score calculation and ranking
   - Cache invalidation logic

2. **Integration Tests (15+ specs)**
   - End-to-end recommendation flow
   - Kafka event consumption and production
   - Redis cache integration
   - Database queries with proper indexing

3. **Concurrency Tests (5+ specs)**
   - Thread-safe interaction recording
   - Cache stampede prevention
   - Concurrent recommendation requests

4. **Performance Requirements**
   - Recommendations returned in < 100ms (cached)
   - Recommendations returned in < 500ms (uncached)
   - Batch processing handles 10,000+ events/minute

5. **Architectural Compliance**
   - Follow existing service patterns (see `services/orders/`)
   - Use BigDecimal for similarity scores
   - Implement proper error handling with custom exceptions
   - Add comprehensive YARD documentation

---

## Task 2: Gift Card Service

### Overview

Implement a gift card system supporting purchase, redemption, balance management, and multi-currency support.

### Location

Create the service in: `services/gift_cards/`

### Interface Contract

```ruby
# frozen_string_literal: true

module ShopStream
  module GiftCards
    # Manages gift card lifecycle and transactions
    #
    # @example Creating and redeeming a gift card
    #   service = GiftCardService.new
    #   card = service.create(amount: 50.00, currency: 'USD', purchaser_id: 'user_123')
    #   service.redeem(code: card.code, order_id: 'order_456', amount: 25.00)
    #
    class GiftCardService
      # Create a new gift card
      #
      # @param amount [BigDecimal, Float] Initial balance
      # @param currency [String] ISO 4217 currency code (default: 'USD')
      # @param purchaser_id [String] User who purchased the card
      # @param recipient_email [String, nil] Email to send gift card to
      # @param message [String, nil] Personal message from purchaser
      # @param expires_at [Time, nil] Expiration date (default: 1 year from now)
      # @return [GiftCard] The created gift card
      # @raise [InvalidAmountError] if amount is invalid
      # @raise [UnsupportedCurrencyError] if currency not supported
      def create(amount:, currency: 'USD', purchaser_id:, recipient_email: nil, message: nil, expires_at: nil)
      end

      # Redeem a gift card against an order
      #
      # @param code [String] The gift card redemption code
      # @param order_id [String] The order to apply the gift card to
      # @param amount [BigDecimal, Float, nil] Amount to redeem (default: full balance or order total)
      # @return [RedemptionResult] Result containing redeemed amount and remaining balance
      # @raise [InvalidCodeError] if code is invalid or not found
      # @raise [ExpiredCardError] if gift card has expired
      # @raise [InsufficientBalanceError] if requested amount exceeds balance
      # @raise [AlreadyRedeemedError] if card has zero balance
      def redeem(code:, order_id:, amount: nil)
      end

      # Check gift card balance and status
      #
      # @param code [String] The gift card code
      # @return [BalanceResult] Balance info including original amount, current balance, status
      # @raise [InvalidCodeError] if code is invalid
      def check_balance(code:)
      end

      # Refund a previously redeemed amount back to the gift card
      #
      # @param redemption_id [String] The original redemption transaction ID
      # @param amount [BigDecimal, Float, nil] Amount to refund (default: full redemption amount)
      # @return [RefundResult] Result containing refunded amount and new balance
      # @raise [RedemptionNotFoundError] if redemption doesn't exist
      # @raise [RefundExceedsRedemptionError] if refund amount > original redemption
      def refund_to_card(redemption_id:, amount: nil)
      end

      # Transfer balance between gift cards
      #
      # @param from_code [String] Source gift card code
      # @param to_code [String] Destination gift card code
      # @param amount [BigDecimal, Float] Amount to transfer
      # @return [TransferResult] Result with new balances for both cards
      # @raise [InvalidCodeError] if either code is invalid
      # @raise [InsufficientBalanceError] if source has insufficient funds
      # @raise [CurrencyMismatchError] if cards have different currencies
      def transfer(from_code:, to_code:, amount:)
      end

      # Void/cancel a gift card (admin only)
      #
      # @param code [String] The gift card code
      # @param reason [String] Reason for voiding
      # @param admin_id [String] Admin performing the action
      # @return [Boolean] Whether void was successful
      def void(code:, reason:, admin_id:)
      end

      # Generate bulk gift cards (for promotions)
      #
      # @param count [Integer] Number of cards to generate
      # @param amount [BigDecimal, Float] Amount per card
      # @param currency [String] Currency for all cards
      # @param prefix [String] Code prefix for identification
      # @param expires_at [Time, nil] Expiration for all cards
      # @return [Array<GiftCard>] Generated gift cards
      def bulk_create(count:, amount:, currency: 'USD', prefix: 'PROMO', expires_at: nil)
      end
    end

    # Handles gift card code generation and validation
    class CodeGenerator
      # Generate a unique, secure gift card code
      #
      # @param prefix [String] Optional code prefix
      # @param length [Integer] Code length excluding prefix (default: 16)
      # @return [String] Generated code (e.g., "GIFT-XXXX-XXXX-XXXX-XXXX")
      def generate(prefix: 'GIFT', length: 16)
      end

      # Validate code format and checksum
      #
      # @param code [String] Code to validate
      # @return [Boolean] Whether code format is valid
      def valid_format?(code)
      end
    end

    # Result objects for service operations
    class RedemptionResult
      attr_reader :redemption_id, :redeemed_amount, :remaining_balance, :gift_card
    end

    class BalanceResult
      attr_reader :code, :original_amount, :current_balance, :currency, :status, :expires_at
    end

    class RefundResult
      attr_reader :refund_id, :refunded_amount, :new_balance
    end

    class TransferResult
      attr_reader :transfer_id, :amount, :from_balance, :to_balance
    end
  end
end
```

### Required Models

```ruby
# services/gift_cards/app/models/gift_card.rb
class GiftCard < ApplicationRecord
  # Columns: id, code, original_amount, current_balance, currency, status,
  #          purchaser_id, recipient_email, message, expires_at, voided_at,
  #          voided_by, void_reason, created_at, updated_at

  STATUSES = %w[active partially_redeemed fully_redeemed expired voided].freeze

  validates :code, presence: true, uniqueness: true
  validates :original_amount, :current_balance, numericality: { greater_than_or_equal_to: 0 }
  validates :currency, presence: true
  validates :status, inclusion: { in: STATUSES }

  has_many :transactions, class_name: 'GiftCardTransaction'
  has_many :redemptions, -> { where(transaction_type: 'redemption') }, class_name: 'GiftCardTransaction'

  scope :active, -> { where(status: 'active') }
  scope :with_balance, -> { where('current_balance > 0') }
  scope :expired, -> { where('expires_at < ?', Time.current) }
end

# services/gift_cards/app/models/gift_card_transaction.rb
class GiftCardTransaction < ApplicationRecord
  # Columns: id, gift_card_id, transaction_type, amount, balance_before, balance_after,
  #          order_id, reference_id, metadata (jsonb), created_at

  TRANSACTION_TYPES = %w[creation redemption refund transfer_in transfer_out void].freeze

  belongs_to :gift_card

  validates :transaction_type, inclusion: { in: TRANSACTION_TYPES }
  validates :amount, numericality: true
end
```

### Kafka Event Integration

Subscribe to these events:
- `order.refunded` - Trigger refund back to gift card if applicable
- `order.cancelled` - Release any gift card redemptions

Publish these events:
- `gift_card.created` - New gift card issued
- `gift_card.redeemed` - Gift card used on order
- `gift_card.refunded` - Amount returned to gift card
- `gift_card.expired` - Gift card reached expiration
- `gift_card.voided` - Gift card cancelled by admin

### Acceptance Criteria

1. **Unit Tests (50+ specs)**
   - Gift card creation with all options
   - Code generation uniqueness and format
   - Redemption with partial and full amounts
   - Balance calculations with BigDecimal precision
   - Refund and transfer operations
   - Expiration handling
   - Void functionality

2. **Integration Tests (20+ specs)**
   - Full purchase-to-redemption flow
   - Multi-step redemption across orders
   - Refund back to gift card
   - Bulk creation for promotions
   - Kafka event publishing

3. **Concurrency Tests (10+ specs)**
   - Concurrent redemption attempts (prevent double-spend)
   - Race condition in balance updates
   - Distributed lock for transfers
   - Atomic transaction recording

4. **Financial Precision Tests (10+ specs)**
   - No floating-point errors in calculations
   - Currency handling and validation
   - Rounding consistency
   - Audit trail completeness

5. **Security Tests (5+ specs)**
   - Code generation entropy
   - Timing-safe code comparison
   - Rate limiting on balance checks
   - Admin action authorization

---

## Task 3: Returns Processing System

### Overview

Implement a returns management system handling return requests, approvals, refund processing, and inventory restocking.

### Location

Create the service in: `services/returns/`

### Interface Contract

```ruby
# frozen_string_literal: true

module ShopStream
  module Returns
    # Manages the complete returns lifecycle
    #
    # @example Processing a return
    #   service = ReturnsService.new
    #   request = service.initiate(order_id: 'order_123', items: [...], reason: :defective)
    #   service.approve(return_id: request.id, refund_method: :original_payment)
    #   service.complete(return_id: request.id, items_received: [...])
    #
    class ReturnsService
      # Initiate a return request
      #
      # @param order_id [String] The original order ID
      # @param items [Array<Hash>] Items to return with quantities
      #   @option items [String] :line_item_id Original line item ID
      #   @option items [Integer] :quantity Quantity to return
      #   @option items [String] :condition Item condition (new, opened, damaged)
      # @param reason [Symbol] Return reason (:defective, :wrong_item, :not_as_described, :no_longer_needed, :other)
      # @param description [String, nil] Additional details about the return
      # @param images [Array<String>] URLs of photos showing item condition
      # @return [ReturnRequest] The created return request
      # @raise [OrderNotFoundError] if order doesn't exist
      # @raise [ReturnWindowExpiredError] if return period has passed
      # @raise [ItemNotReturnableError] if item is not eligible for return
      # @raise [InvalidQuantityError] if quantity exceeds original purchase
      def initiate(order_id:, items:, reason:, description: nil, images: [])
      end

      # Approve a return request
      #
      # @param return_id [String] The return request ID
      # @param refund_method [Symbol] How to process refund (:original_payment, :store_credit, :gift_card, :exchange)
      # @param refund_amount [BigDecimal, nil] Override calculated refund (for partial refunds)
      # @param restocking_fee [BigDecimal] Fee to deduct (default: 0)
      # @param notes [String, nil] Approval notes
      # @param approver_id [String] ID of staff member approving
      # @return [ApprovalResult] Result with shipping label and instructions
      # @raise [ReturnNotFoundError] if return doesn't exist
      # @raise [InvalidStateError] if return is not pending
      def approve(return_id:, refund_method:, refund_amount: nil, restocking_fee: 0, notes: nil, approver_id:)
      end

      # Reject a return request
      #
      # @param return_id [String] The return request ID
      # @param reason [String] Reason for rejection
      # @param rejector_id [String] ID of staff member rejecting
      # @return [Boolean] Whether rejection was recorded
      def reject(return_id:, reason:, rejector_id:)
      end

      # Mark items as received at warehouse
      #
      # @param return_id [String] The return request ID
      # @param items_received [Array<Hash>] Items received with condition assessment
      #   @option items_received [String] :line_item_id
      #   @option items_received [Integer] :quantity_received
      #   @option items_received [String] :actual_condition (:sellable, :damaged, :unsellable)
      #   @option items_received [String, nil] :notes
      # @param receiver_id [String] Warehouse staff ID
      # @return [ReceiptResult] Updated return status and any adjustments
      def receive_items(return_id:, items_received:, receiver_id:)
      end

      # Complete the return and process refund
      #
      # @param return_id [String] The return request ID
      # @param final_refund_amount [BigDecimal, nil] Override if condition differs from expected
      # @return [CompletionResult] Refund transaction details
      # @raise [ItemsNotReceivedError] if items haven't been marked received
      def complete(return_id:, final_refund_amount: nil)
      end

      # Cancel a return request (by customer before shipping)
      #
      # @param return_id [String] The return request ID
      # @param reason [String, nil] Cancellation reason
      # @return [Boolean] Whether cancellation succeeded
      def cancel(return_id:, reason: nil)
      end

      # Get return eligibility for an order
      #
      # @param order_id [String] The order ID
      # @return [EligibilityResult] Which items can be returned and why
      def check_eligibility(order_id:)
      end

      # Generate return shipping label
      #
      # @param return_id [String] The return request ID
      # @return [ShippingLabel] Label URL and tracking number
      def generate_shipping_label(return_id:)
      end
    end

    # Calculates refund amounts based on return policy
    class RefundCalculator
      # Calculate refund for returned items
      #
      # @param return_request [ReturnRequest] The return request
      # @param restocking_fee_percent [Float] Percentage fee (default: 0)
      # @param condition_adjustments [Hash] Adjustments by condition
      # @return [RefundBreakdown] Detailed refund calculation
      def calculate(return_request:, restocking_fee_percent: 0, condition_adjustments: {})
      end
    end

    # Manages return policy rules
    class PolicyEngine
      # Check if item is returnable
      #
      # @param line_item [LineItem] The order line item
      # @param order [Order] The original order
      # @return [PolicyResult] Whether returnable and any restrictions
      def check_item(line_item:, order:)
      end

      # Get return window for order
      #
      # @param order [Order] The order to check
      # @return [Integer] Days remaining in return window (negative if expired)
      def return_window_remaining(order:)
      end
    end

    # Result objects
    class ReturnRequest
      attr_reader :id, :order_id, :status, :items, :reason, :created_at
    end

    class ApprovalResult
      attr_reader :return_id, :approved_at, :shipping_label, :instructions, :estimated_refund
    end

    class ReceiptResult
      attr_reader :items_status, :condition_adjustments, :adjusted_refund
    end

    class CompletionResult
      attr_reader :refund_transaction_id, :refund_amount, :refund_method, :inventory_updates
    end

    class EligibilityResult
      attr_reader :eligible_items, :ineligible_items, :return_window_expires_at
    end

    class RefundBreakdown
      attr_reader :item_total, :tax_refund, :shipping_refund, :restocking_fee, :total_refund
    end
  end
end
```

### Required Models

```ruby
# services/returns/app/models/return_request.rb
class ReturnRequest < ApplicationRecord
  include AASM

  # Columns: id, order_id, customer_id, status, reason, description,
  #          refund_method, estimated_refund, actual_refund, restocking_fee,
  #          shipping_label_url, tracking_number, approved_by, approved_at,
  #          received_at, completed_at, cancelled_at, created_at, updated_at

  REASONS = %w[defective wrong_item not_as_described no_longer_needed other].freeze
  REFUND_METHODS = %w[original_payment store_credit gift_card exchange].freeze

  has_many :return_items
  belongs_to :order

  validates :reason, inclusion: { in: REASONS }

  aasm column: :status do
    state :pending, initial: true
    state :approved
    state :shipped
    state :received
    state :inspecting
    state :completed
    state :rejected
    state :cancelled

    event :approve do
      transitions from: :pending, to: :approved
    end

    event :ship do
      transitions from: :approved, to: :shipped
    end

    event :receive do
      transitions from: :shipped, to: :received
    end

    event :inspect do
      transitions from: :received, to: :inspecting
    end

    event :complete do
      transitions from: [:received, :inspecting], to: :completed
    end

    event :reject do
      transitions from: :pending, to: :rejected
    end

    event :cancel do
      transitions from: [:pending, :approved], to: :cancelled
    end
  end
end

# services/returns/app/models/return_item.rb
class ReturnItem < ApplicationRecord
  # Columns: id, return_request_id, line_item_id, product_id, quantity_requested,
  #          quantity_received, expected_condition, actual_condition,
  #          unit_refund_amount, restockable, notes, created_at, updated_at

  CONDITIONS = %w[new opened damaged].freeze
  ACTUAL_CONDITIONS = %w[sellable damaged unsellable].freeze

  belongs_to :return_request
  belongs_to :line_item

  validates :quantity_requested, numericality: { greater_than: 0 }
  validates :expected_condition, inclusion: { in: CONDITIONS }
  validates :actual_condition, inclusion: { in: ACTUAL_CONDITIONS }, allow_nil: true
end

# services/returns/app/models/return_audit_log.rb
class ReturnAuditLog < ApplicationRecord
  # Columns: id, return_request_id, action, actor_id, actor_type,
  #          previous_state, new_state, metadata (jsonb), created_at

  belongs_to :return_request

  scope :for_return, ->(return_id) { where(return_request_id: return_id) }
  scope :recent, -> { order(created_at: :desc) }
end
```

### Kafka Event Integration

Subscribe to these events:
- `order.completed` - Enable return eligibility tracking
- `shipment.delivered` - Start return window countdown

Publish these events:
- `return.initiated` - Customer started return
- `return.approved` - Return approved, awaiting shipment
- `return.received` - Items received at warehouse
- `return.completed` - Refund processed
- `return.rejected` - Return denied
- `inventory.restocked` - Items returned to inventory

### Integration Points

- **Orders Service**: Fetch order details, update order status
- **Inventory Service**: Restock items, update stock levels
- **Payments Service**: Process refunds via RefundService
- **Gift Cards Service**: Issue store credit as gift card
- **Notifications Service**: Send return status emails
- **Shipping Service**: Generate return labels

### Acceptance Criteria

1. **Unit Tests (60+ specs)**
   - Return initiation with all reason types
   - Eligibility checking and policy enforcement
   - Refund calculation with restocking fees
   - State machine transitions
   - Condition assessment impact on refund
   - Audit logging

2. **Integration Tests (25+ specs)**
   - Full return lifecycle (initiate -> approve -> receive -> complete)
   - Refund processing through Payments service
   - Inventory restocking flow
   - Gift card issuance for store credit
   - Notification delivery

3. **Policy Tests (15+ specs)**
   - Return window enforcement
   - Non-returnable item handling
   - Category-specific rules
   - Restocking fee calculations

4. **Saga/Compensation Tests (10+ specs)**
   - Refund failure handling
   - Partial receipt processing
   - Inventory sync failures
   - Rollback on errors

5. **Financial Precision Tests (10+ specs)**
   - BigDecimal calculations throughout
   - Tax refund proportionality
   - Multi-item return calculations
   - Shipping refund rules

6. **Audit and Compliance Tests (5+ specs)**
   - Complete audit trail for all actions
   - Actor tracking (customer vs staff)
   - State change logging
   - Immutable history

---

## General Requirements for All Tasks

### Architectural Patterns

Follow these patterns from existing ShopStream services:

1. **Service Classes**: Business logic in `app/services/`, models are thin
2. **Result Objects**: Return structured results, not primitives
3. **Custom Exceptions**: Define in `app/errors/` with descriptive names
4. **YARD Documentation**: All public methods fully documented
5. **Frozen String Literals**: Add `# frozen_string_literal: true` to all files
6. **BigDecimal for Money**: Never use Float for financial calculations
7. **Kafka Events**: Use `KafkaProducer.publish` for outbound events
8. **Redis Caching**: Use for performance-critical data
9. **Distributed Locks**: Use `LockService` pattern for critical sections
10. **State Machines**: Use AASM gem for status workflows

### Testing Standards

- Use RSpec with FactoryBot for fixtures
- Achieve 95%+ line coverage
- Include request specs for API endpoints
- Mock external services (Kafka, Redis) in unit tests
- Use real services in integration tests (Docker)
- Test edge cases and error conditions

### File Structure Example

```
services/[service_name]/
  app/
    controllers/
      api/
        v1/
          [resource]_controller.rb
    models/
      [model].rb
    services/
      [service].rb
    jobs/
      [job].rb
    consumers/
      [event]_consumer.rb
    errors/
      [error].rb
  config/
    routes.rb
    sidekiq.yml
  db/
    migrate/
  spec/
    models/
    services/
    controllers/
    jobs/
    consumers/
    factories/
    rails_helper.rb
  Gemfile
```
