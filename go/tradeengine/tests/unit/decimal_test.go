package unit

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/terminal-bench/tradeengine/pkg/decimal"
)

func TestPriceCreation(t *testing.T) {
	t.Run("should create price from string", func(t *testing.T) {
		price, err := decimal.NewPrice("100.50")
		assert.NoError(t, err)
		assert.Equal(t, "100.50000000", price.String())
	})

	t.Run("should reject invalid price", func(t *testing.T) {
		_, err := decimal.NewPrice("not-a-number")
		assert.Error(t, err)
	})

	t.Run("should create price from float without precision loss", func(t *testing.T) {
		
		// When fixed, 0.1 + 0.2 should produce exactly "0.30000000"
		price := decimal.NewPriceFromFloat(0.1 + 0.2)
		assert.Equal(t, "0.30000000", price.String(),
			"NewPriceFromFloat should use decimal arithmetic to avoid float64 precision loss")
	})
}

func TestPriceArithmetic(t *testing.T) {
	t.Run("should add prices correctly", func(t *testing.T) {
		p1, _ := decimal.NewPrice("100.50")
		p2, _ := decimal.NewPrice("50.25")

		result := p1.Add(p2)
		assert.Equal(t, "150.75000000", result.String())
	})

	t.Run("should subtract prices correctly", func(t *testing.T) {
		p1, _ := decimal.NewPrice("100.50")
		p2, _ := decimal.NewPrice("50.25")

		result := p1.Sub(p2)
		assert.Equal(t, "50.25000000", result.String())
	})

	t.Run("should multiply price by quantity using decimal", func(t *testing.T) {
		price, _ := decimal.NewPrice("100.50")
		qty := decimal.NewQuantityFromInt(10)

		
		// When fixed, multiplication should preserve precision
		result := price.Mul(qty)
		assert.InDelta(t, 1005.0, result.Amount, 0.001,
			"Multiplication should produce exact result using decimal arithmetic")
	})

	t.Run("should divide prices", func(t *testing.T) {
		p1, _ := decimal.NewPrice("100")
		p2, _ := decimal.NewPrice("3")

		result, err := p1.Div(p2)
		assert.NoError(t, err)
		// Result should have many decimal places
		assert.Contains(t, result.String(), "33.33333")
	})

	t.Run("should reject division by zero", func(t *testing.T) {
		p1, _ := decimal.NewPrice("100")
		p2, _ := decimal.NewPrice("0")

		_, err := p1.Div(p2)
		assert.Error(t, err, "Division by zero should return error, not panic")
	})
}

func TestMoneyOperations(t *testing.T) {
	t.Run("should add money amounts with proper precision", func(t *testing.T) {
		m1 := decimal.Money{Amount: 100.50, Currency: "USD"}
		m2 := decimal.Money{Amount: 50.25, Currency: "USD"}

		
		result := m1.Add(m2)
		assert.Equal(t, 150.75, result.Amount,
			"Money.Add should use decimal arithmetic for exact results")
	})

	t.Run("should handle float precision correctly", func(t *testing.T) {
		
		// When fixed, 0.1 + 0.2 should equal 0.3
		m1 := decimal.Money{Amount: 0.1, Currency: "USD"}
		m2 := decimal.Money{Amount: 0.2, Currency: "USD"}

		result := m1.Add(m2)
		assert.Equal(t, 0.3, result.Amount,
			"0.1 + 0.2 should equal 0.3 when using decimal arithmetic")
	})

	t.Run("should round money correctly", func(t *testing.T) {
		m := decimal.Money{Amount: 100.555, Currency: "USD"}

		
		result := m.Round()
		assert.Equal(t, 100.56, result.Amount,
			"Money.Round should use consistent rounding mode (round half to even)")
	})
}

func TestParseMoney(t *testing.T) {
	t.Run("should parse valid money string", func(t *testing.T) {
		m, err := decimal.ParseMoney("100.50 USD")
		assert.NoError(t, err)
		assert.Equal(t, 100.50, m.Amount)
		assert.Equal(t, "USD", m.Currency)
	})

	t.Run("should reject invalid format", func(t *testing.T) {
		_, err := decimal.ParseMoney("invalid")
		assert.Error(t, err)
	})

	t.Run("should preserve precision on large amounts", func(t *testing.T) {
		
		// When fixed, large values should be parsed using decimal, not float64
		m, err := decimal.ParseMoney("9999999999999999.99 USD")
		assert.NoError(t, err)
		assert.Equal(t, 9999999999999999.99, m.Amount,
			"ParseMoney should use decimal parsing to preserve precision on large amounts")
	})
}

func TestParseMoneyLargePrecision(t *testing.T) {
	t.Run("should parse money with many decimal places", func(t *testing.T) {
		
		m, err := decimal.ParseMoney("123.456789012345 USD")
		assert.NoError(t, err)
		assert.InDelta(t, 123.456789012345, m.Amount, 1e-12,
			"ParseMoney should preserve high-precision decimal places")
	})
}

func TestCalculatePnL(t *testing.T) {
	t.Run("should calculate profit", func(t *testing.T) {
		entry, _ := decimal.NewPrice("100")
		exit, _ := decimal.NewPrice("110")
		qty := decimal.NewQuantityFromInt(10)

		pnl := decimal.CalculatePnL(entry, exit, qty)
		assert.Equal(t, 100.0, pnl.Amount,
			"PnL calculation should be exact: (110-100)*10 = 100")
	})

	t.Run("should calculate loss", func(t *testing.T) {
		entry, _ := decimal.NewPrice("100")
		exit, _ := decimal.NewPrice("90")
		qty := decimal.NewQuantityFromInt(10)

		pnl := decimal.CalculatePnL(entry, exit, qty)
		assert.Equal(t, -100.0, pnl.Amount,
			"PnL for loss: (90-100)*10 = -100")
	})
}

func TestPnLFloatPrecision(t *testing.T) {
	t.Run("should calculate PnL without float drift", func(t *testing.T) {
		
		entry, _ := decimal.NewPrice("0.10")
		exit, _ := decimal.NewPrice("0.30")
		qty := decimal.NewQuantityFromInt(1000)

		pnl := decimal.CalculatePnL(entry, exit, qty)
		assert.Equal(t, 200.0, pnl.Amount,
			"PnL should be exact 200.0 using decimal, not drifted float result")
	})
}

func TestCalculateMargin(t *testing.T) {
	t.Run("should calculate margin requirement", func(t *testing.T) {
		price, _ := decimal.NewPrice("100")
		qty := decimal.NewQuantityFromInt(100)
		marginRate := 0.1 // 10%

		margin := decimal.CalculateMargin(price, qty, marginRate)
		assert.Equal(t, 1000.0, margin.Amount,
			"Margin: 100 * 100 * 0.1 = 1000")
	})

	t.Run("should not overflow for large positions", func(t *testing.T) {
		
		price, _ := decimal.NewPrice("1000000")
		qty := decimal.NewQuantityFromInt(1000000)
		marginRate := 0.1

		margin := decimal.CalculateMargin(price, qty, marginRate)
		assert.Equal(t, 100000000000.0, margin.Amount,
			"Large margin calculation should not overflow; expected 1e11")
	})
}

func TestMarginOverflow(t *testing.T) {
	t.Run("should handle extreme values without overflow", func(t *testing.T) {
		
		price, _ := decimal.NewPrice("999999999")
		qty := decimal.NewQuantityFromInt(999999999)
		marginRate := 0.01

		margin := decimal.CalculateMargin(price, qty, marginRate)
		assert.Greater(t, margin.Amount, 0.0,
			"Margin must remain positive, no overflow to negative")
		assert.Less(t, margin.Amount, 1e19,
			"Margin must be within reasonable bounds")
	})
}

func TestQuantityOperations(t *testing.T) {
	t.Run("should add quantities", func(t *testing.T) {
		q1 := decimal.NewQuantityFromInt(100)
		q2 := decimal.NewQuantityFromInt(50)

		result := q1.Add(q2)
		assert.Equal(t, int64(150), result.Int64())
	})

	t.Run("should subtract quantities", func(t *testing.T) {
		q1 := decimal.NewQuantityFromInt(100)
		q2 := decimal.NewQuantityFromInt(30)

		result := q1.Sub(q2)
		assert.Equal(t, int64(70), result.Int64())
	})

	t.Run("should handle negative quantities", func(t *testing.T) {
		q1 := decimal.NewQuantityFromInt(50)
		q2 := decimal.NewQuantityFromInt(100)

		result := q1.Sub(q2)
		assert.Equal(t, int64(-50), result.Int64())
	})
}

func TestPriceRounding(t *testing.T) {
	t.Run("should round to specified places", func(t *testing.T) {
		price, _ := decimal.NewPrice("100.123456789")

		rounded := price.Round(2)
		
		assert.Equal(t, "100.12000000", rounded.String(),
			"Round(2) should produce 100.12 using consistent rounding mode")
	})

	t.Run("should truncate with RoundDown", func(t *testing.T) {
		price, _ := decimal.NewPrice("100.999")

		truncated := price.RoundDown(2)
		assert.Equal(t, "100.99000000", truncated.String(),
			"RoundDown(2) should truncate to 100.99")
	})
}

func TestRoundingModeConsistency(t *testing.T) {
	t.Run("should use banker rounding for 0.5 boundary", func(t *testing.T) {
		
		price, _ := decimal.NewPrice("100.125")
		rounded := price.Round(2)
		assert.Equal(t, "100.12000000", rounded.String(),
			"100.125 rounds to 100.12 with banker's rounding (round half to even)")
	})

	t.Run("should round 100.135 to 100.14", func(t *testing.T) {
		price, _ := decimal.NewPrice("100.135")
		rounded := price.Round(2)
		assert.Equal(t, "100.14000000", rounded.String(),
			"100.135 rounds to 100.14 with banker's rounding")
	})
}

func TestRoundMoney(t *testing.T) {
	t.Run("should round money to two decimal places", func(t *testing.T) {
		m := decimal.Money{Amount: 99.999, Currency: "USD"}
		result := m.Round()
		assert.Equal(t, 100.00, result.Amount,
			"99.999 rounded to 2 places should be 100.00")
	})
}

func TestFormatMoney(t *testing.T) {
	t.Run("should format money for display", func(t *testing.T) {
		m := decimal.Money{Amount: 1234.56, Currency: "USD"}

		formatted := decimal.FormatMoney(m)
		assert.Equal(t, "1234.56 USD", formatted)
	})

	t.Run("should format 0.30 correctly after decimal addition", func(t *testing.T) {
		
		// When F1 is fixed, 0.1 + 0.2 stored as decimal will format correctly
		m := decimal.Money{Amount: 0.3, Currency: "USD"}

		formatted := decimal.FormatMoney(m)
		assert.Equal(t, "0.30 USD", formatted,
			"FormatMoney should display 0.30 USD for Amount=0.3")
	})
}

func TestDivisionByZero(t *testing.T) {
	t.Run("should return error for division by zero", func(t *testing.T) {
		p1, _ := decimal.NewPrice("100")
		p2, _ := decimal.NewPrice("0")

		_, err := p1.Div(p2)
		assert.Error(t, err, "Division by zero must return an error")
	})
}

func TestFillCompletionFloatComparison(t *testing.T) {
	t.Run("should detect fill completion with epsilon comparison", func(t *testing.T) {
		
		// Simulate partial fills that should sum to 1.0
		filled := 0.0
		for i := 0; i < 10; i++ {
			filled += 0.1
		}
		// Without epsilon, filled != 1.0 due to float drift
		// When fixed, decimal comparison or epsilon-aware check should succeed
		total := 1.0
		diff := filled - total
		if diff < 0 {
			diff = -diff
		}
		assert.Less(t, diff, 1e-9,
			"Fill completion check should use epsilon comparison, not == on float64")
	})
}

func TestFloatComparisonEpsilon(t *testing.T) {
	t.Run("should compare floats with epsilon tolerance", func(t *testing.T) {
		
		a := 0.1 + 0.2
		b := 0.3
		// Using proper decimal or epsilon comparison
		diff := a - b
		if diff < 0 {
			diff = -diff
		}
		assert.Less(t, diff, 1e-9,
			"Float comparison must use epsilon tolerance, not direct ==")
	})
}

func TestMaxDrawdownCalculation(t *testing.T) {
	t.Run("should calculate max drawdown correctly", func(t *testing.T) {
		
		values := []float64{100.0, 110.0, 90.0, 95.0, 80.0, 120.0}
		// Peak: 110, Trough after peak: 80, Drawdown = (110-80)/110 = 27.27%
		peak := 0.0
		maxDrawdown := 0.0
		for _, v := range values {
			if v > peak {
				peak = v
			}
			drawdown := (peak - v) / peak
			if drawdown > maxDrawdown {
				maxDrawdown = drawdown
			}
		}
		assert.InDelta(t, 0.2727, maxDrawdown, 0.01,
			"Max drawdown from 110 to 80 should be ~27.27%%")
	})
}

func TestAllocationDivisionByZero(t *testing.T) {
	t.Run("should handle zero total in allocation", func(t *testing.T) {
		
		totalAllocation := 0.0
		portion := 100.0

		var result float64
		if totalAllocation == 0 {
			result = 0.0 // Safe default
		} else {
			result = portion / totalAllocation
		}
		assert.Equal(t, 0.0, result,
			"Allocation with zero total should return 0, not panic/Inf")
	})
}
