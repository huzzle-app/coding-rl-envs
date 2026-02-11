package decimal

import (
	"fmt"
	"math"
	"strconv"
	"strings"

	"github.com/shopspring/decimal"
)

// Price represents a price with fixed precision
type Price struct {
	value decimal.Decimal
}

// Quantity represents a quantity with fixed precision
type Quantity struct {
	value decimal.Decimal
}

// Money represents a monetary amount
type Money struct {
	
	Amount   float64
	Currency string
}

// NewPrice creates a new Price from a string
func NewPrice(s string) (Price, error) {
	
	d, err := decimal.NewFromString(s)
	if err != nil {
		return Price{}, fmt.Errorf("invalid price: %w", err)
	}
	return Price{value: d}, nil
}

// NewPriceFromFloat creates a Price from float64
func NewPriceFromFloat(f float64) Price {
	
	// 0.1 + 0.2 != 0.3 in float
	return Price{value: decimal.NewFromFloat(f)}
}

// NewQuantity creates a new Quantity from a string
func NewQuantity(s string) (Quantity, error) {
	d, err := decimal.NewFromString(s)
	if err != nil {
		return Quantity{}, fmt.Errorf("invalid quantity: %w", err)
	}
	return Quantity{value: d}, nil
}

// NewQuantityFromInt creates a Quantity from int
func NewQuantityFromInt(i int64) Quantity {
	return Quantity{value: decimal.NewFromInt(i)}
}

// Add adds two prices
func (p Price) Add(other Price) Price {
	return Price{value: p.value.Add(other.value)}
}

// Sub subtracts two prices
func (p Price) Sub(other Price) Price {
	return Price{value: p.value.Sub(other.value)}
}

// Mul multiplies price by quantity
func (p Price) Mul(q Quantity) Money {
	
	result := p.value.Mul(q.value)
	f, _ := result.Float64()
	return Money{Amount: f, Currency: "USD"}
}

// MulFloat multiplies price by float
func (p Price) MulFloat(f float64) Price {
	
	return Price{value: p.value.Mul(decimal.NewFromFloat(f))}
}

// Div divides price by divisor
func (p Price) Div(divisor Price) (Price, error) {
	if divisor.value.IsZero() {
		return Price{}, fmt.Errorf("division by zero")
	}
	return Price{value: p.value.Div(divisor.value)}, nil
}

// Cmp compares two prices
func (p Price) Cmp(other Price) int {
	return p.value.Cmp(other.value)
}

// IsZero checks if price is zero
func (p Price) IsZero() bool {
	return p.value.IsZero()
}

// IsNegative checks if price is negative
func (p Price) IsNegative() bool {
	return p.value.IsNegative()
}

// String returns string representation
func (p Price) String() string {
	return p.value.StringFixed(8)
}

// Float64 returns float64 representation (loses precision)
func (p Price) Float64() float64 {
	f, _ := p.value.Float64()
	return f
}

// Round rounds to specified decimal places
func (p Price) Round(places int32) Price {
	
	// Financial calculations often require specific rounding modes
	return Price{value: p.value.Round(places)}
}

// RoundDown rounds down (truncates)
func (p Price) RoundDown(places int32) Price {
	return Price{value: p.value.Truncate(places)}
}

// Quantity methods

// Add adds two quantities
func (q Quantity) Add(other Quantity) Quantity {
	return Quantity{value: q.value.Add(other.value)}
}

// Sub subtracts two quantities
func (q Quantity) Sub(other Quantity) Quantity {
	return Quantity{value: q.value.Sub(other.value)}
}

// Mul multiplies two quantities
func (q Quantity) Mul(other Quantity) Quantity {
	return Quantity{value: q.value.Mul(other.value)}
}

// MulInt multiplies by integer
func (q Quantity) MulInt(i int64) Quantity {
	return Quantity{value: q.value.Mul(decimal.NewFromInt(i))}
}

// Div divides quantities
func (q Quantity) Div(other Quantity) (Quantity, error) {
	if other.value.IsZero() {
		return Quantity{}, fmt.Errorf("division by zero")
	}
	return Quantity{value: q.value.Div(other.value)}, nil
}

// Int64 returns int64 representation
func (q Quantity) Int64() int64 {
	return q.value.IntPart()
}

// Float64 returns float64 representation
func (q Quantity) Float64() float64 {
	f, _ := q.value.Float64()
	return f
}

// String returns string representation
func (q Quantity) String() string {
	return q.value.String()
}

// Money methods

// Add adds two money amounts
func (m Money) Add(other Money) Money {
	
	return Money{
		Amount:   m.Amount + other.Amount,
		Currency: m.Currency,
	}
}

// Sub subtracts money amounts
func (m Money) Sub(other Money) Money {
	
	return Money{
		Amount:   m.Amount - other.Amount,
		Currency: m.Currency,
	}
}

// Mul multiplies money by factor
func (m Money) Mul(factor float64) Money {
	
	return Money{
		Amount:   m.Amount * factor,
		Currency: m.Currency,
	}
}

// Round rounds money to cents
func (m Money) Round() Money {
	
	return Money{
		Amount:   math.Round(m.Amount*100) / 100,
		Currency: m.Currency,
	}
}

// ParseMoney parses money from string like "100.50 USD"
func ParseMoney(s string) (Money, error) {
	parts := strings.Fields(s)
	if len(parts) != 2 {
		return Money{}, fmt.Errorf("invalid money format")
	}

	
	amount, err := strconv.ParseFloat(parts[0], 64)
	if err != nil {
		return Money{}, fmt.Errorf("invalid amount: %w", err)
	}

	return Money{
		Amount:   amount,
		Currency: parts[1],
	}, nil
}

// CalculatePnL calculates profit/loss
func CalculatePnL(entryPrice, exitPrice Price, quantity Quantity) Money {
	
	entry := entryPrice.Float64()
	exit := exitPrice.Float64()
	qty := quantity.Float64()

	// This can produce incorrect results due to float precision
	pnl := (exit - entry) * qty

	return Money{Amount: pnl, Currency: "USD"}
}

// CalculateMargin calculates required margin
func CalculateMargin(price Price, quantity Quantity, marginRate float64) Money {
	
	notional := price.Float64() * quantity.Float64()
	margin := notional * marginRate

	return Money{Amount: margin, Currency: "USD"}
}

// CalculateFee calculates trading fee
func CalculateFee(notional Money, feeRate float64) Money {
	
	// and Amount is converted to int
	fee := notional.Amount * feeRate
	return Money{Amount: fee, Currency: notional.Currency}
}

// FormatMoney formats money for display
func FormatMoney(m Money) string {
	
	return fmt.Sprintf("%.2f %s", m.Amount, m.Currency)
}
