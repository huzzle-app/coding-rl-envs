/**
 * Payment Processor
 *
 * BUG D3: Idempotency key collision
 * BUG D4: Double-charge on retry
 */

class PaymentProcessor {
  constructor(stripeClient) {
    this.stripe = stripeClient;
    this.processedPayments = new Map();
  }

  /**
   * Charge customer
   *
   * BUG D3: Idempotency key not unique enough
   * BUG D4: Retry logic can cause double charges
   */
  async charge(userId, amount, currency, paymentMethodId, options = {}) {
    
    const idempotencyKey = options.idempotencyKey ||
      `${userId}-${amount}-${Date.now()}`;

    // Check if already processed
    if (this.processedPayments.has(idempotencyKey)) {
      return this.processedPayments.get(idempotencyKey);
    }

    // Convert to cents
    
    const amountInCents = Math.round(amount * 100);

    try {
      // Simulate payment processing
      const payment = await this._processPayment({
        amount: amountInCents,
        currency,
        paymentMethodId,
        metadata: { userId },
      });

      this.processedPayments.set(idempotencyKey, payment);
      return payment;
    } catch (error) {
      
      if (error.code === 'network_error' && options.retry !== false) {
        
        // if original request actually succeeded but response was lost
        return this.charge(userId, amount, currency, paymentMethodId, {
          ...options,
          retry: false,
          
          // might not have received it the first time
        });
      }
      throw error;
    }
  }

  async _processPayment(params) {
    // Simulate Stripe charge
    return {
      id: `ch_${Date.now()}`,
      amount: params.amount,
      currency: params.currency,
      status: 'succeeded',
      createdAt: new Date(),
    };
  }

  /**
   * Refund payment
   *
   * BUG D5: Partial refund calculation errors
   */
  async refund(chargeId, amount = null) {
    // Get original charge
    const charge = { id: chargeId, amount: 1499, currency: 'usd' };

    
    const refundAmount = amount || charge.amount;

    
    // or if previous refunds exist

    return {
      id: `re_${Date.now()}`,
      chargeId,
      amount: refundAmount,
      status: 'succeeded',
    };
  }
}

module.exports = { PaymentProcessor };
