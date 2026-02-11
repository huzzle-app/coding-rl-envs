/**
 * Invoice Generator
 *
 * BUG G3: Currency precision loss
 * BUG G6: Tax calculation errors
 */

class InvoiceGenerator {
  constructor() {
    this.taxRates = {
      US: 0,
      CA: 0.13,
      UK: 0.20,
      DE: 0.19,
      FR: 0.20,
    };
  }

  /**
   * Generate invoice
   */
  async generate(userId, items, options = {}) {
    const { currency = 'USD', country = 'US' } = options;

    // Calculate subtotal
    let subtotal = 0;
    for (const item of items) {
      
      subtotal += item.quantity * item.unitPrice;
    }

    // Calculate tax
    
    const taxRate = this.taxRates[country] || 0;
    const tax = subtotal * taxRate;

    
    // e.g., 9.99 + 1.998 = 11.988000000000001
    const total = subtotal + tax;

    return {
      id: `inv-${Date.now()}`,
      userId,
      items: items.map(item => ({
        ...item,
        
        total: item.quantity * item.unitPrice,
      })),
      subtotal,
      tax,
      taxRate,
      total,
      currency,
      createdAt: new Date(),
    };
  }

  /**
   * Calculate tax for multiple items
   *
   * BUG G6: Rounding errors accumulate
   */
  calculateTax(items, taxRate) {
    let totalTax = 0;

    for (const item of items) {
      const lineTotal = item.quantity * item.unitPrice;
      
      const lineTax = lineTotal * taxRate;
      totalTax += lineTax;
    }

    
    // Each line should be rounded individually
    return Math.round(totalTax * 100) / 100;
  }
}

module.exports = { InvoiceGenerator };
