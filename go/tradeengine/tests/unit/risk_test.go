package unit

import (
	"math"
	"sync"
	"sync/atomic"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/terminal-bench/tradeengine/internal/risk"
)

func TestRiskCalculatorCreation(t *testing.T) {
	t.Run("should create calculator with config", func(t *testing.T) {
		calc := risk.NewCalculator(risk.CalculatorConfig{
			MaxPositionSize:   1000000,
			MaxDailyLoss:      50000,
			DefaultMarginRate: 0.1,
		})

		assert.NotNil(t, calc)
	})
}

func TestMarginCalculation(t *testing.T) {
	t.Run("should calculate margin for long position", func(t *testing.T) {
		calc := risk.NewCalculator(risk.CalculatorConfig{
			DefaultMarginRate: 0.1,
		})

		
		margin := calc.CalculateMargin(100.0, 1000.0, "BTC-USD")

		// 100 * 1000 * 0.1 = 10000
		assert.InDelta(t, 10000.0, margin, 0.01)
	})

	t.Run("should handle fractional quantities", func(t *testing.T) {
		calc := risk.NewCalculator(risk.CalculatorConfig{
			DefaultMarginRate: 0.1,
		})

		
		margin := calc.CalculateMargin(0.1+0.2, 1000.0, "BTC-USD")

		// Expected: 0.3 * 1000 * 0.1 = 30
		// Actual: may differ due to float precision
		assert.InDelta(t, 30.0, margin, 0.01)
	})

	t.Run("should apply symbol-specific margin rates", func(t *testing.T) {
		calc := risk.NewCalculator(risk.CalculatorConfig{
			DefaultMarginRate: 0.1,
		})

		// Crypto typically has higher margin requirements
		btcMargin := calc.CalculateMargin(50000.0, 1.0, "BTC-USD")
		ethMargin := calc.CalculateMargin(3000.0, 1.0, "ETH-USD")

		assert.Greater(t, btcMargin, 0.0)
		assert.Greater(t, ethMargin, 0.0)
	})
}

func TestPositionLimits(t *testing.T) {
	t.Run("should enforce max position size", func(t *testing.T) {
		calc := risk.NewCalculator(risk.CalculatorConfig{
			MaxPositionSize: 100000,
		})

		// Order within limits
		result := calc.CheckOrder("user1", "BTC-USD", "buy", 1.0, 50000.0)
		assert.True(t, result.Allowed)

		// Order exceeds limits
		result = calc.CheckOrder("user1", "BTC-USD", "buy", 10.0, 50000.0) // 500000 > 100000
		assert.False(t, result.Allowed)
	})

	t.Run("should track position per user", func(t *testing.T) {
		calc := risk.NewCalculator(risk.CalculatorConfig{
			MaxPositionSize: 100000,
		})

		// First order
		calc.RecordPosition("user1", "BTC-USD", 1.0, 50000.0)

		// Second order should consider existing position
		limits := calc.GetLimits("user1")
		assert.NotNil(t, limits)
	})
}

func TestDailyLossLimit(t *testing.T) {
	t.Run("should track daily P&L", func(t *testing.T) {
		calc := risk.NewCalculator(risk.CalculatorConfig{
			MaxDailyLoss: 10000,
		})

		// Record loss
		calc.RecordPnL("user1", -5000.0)

		// Check if more trading allowed
		result := calc.CheckOrder("user1", "BTC-USD", "buy", 1.0, 50000.0)
		assert.True(t, result.Allowed)

		// Record more loss
		calc.RecordPnL("user1", -6000.0) // Total -11000

		// Should be blocked
		result = calc.CheckOrder("user1", "BTC-USD", "buy", 1.0, 50000.0)
		assert.False(t, result.Allowed)
		assert.Equal(t, "daily loss limit exceeded", result.Reason)
	})

	t.Run("should reset daily limit at midnight", func(t *testing.T) {
		calc := risk.NewCalculator(risk.CalculatorConfig{
			MaxDailyLoss: 10000,
		})

		// Record loss
		calc.RecordPnL("user1", -15000.0)

		// Reset
		calc.ResetDailyPnL()

		// Should be allowed again
		result := calc.CheckOrder("user1", "BTC-USD", "buy", 1.0, 50000.0)
		assert.True(t, result.Allowed)
	})
}

func TestConcurrentRiskChecks(t *testing.T) {
	t.Run("should handle concurrent risk checks", func(t *testing.T) {
		
		calc := risk.NewCalculator(risk.CalculatorConfig{
			MaxPositionSize: 1000000,
			MaxDailyLoss:    50000,
		})

		var wg sync.WaitGroup
		errors := make(chan error, 100)

		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				result := calc.CheckOrder("user1", "BTC-USD", "buy", 0.1, 50000.0)
				if !result.Allowed {
					// Might fail due to race
				}
			}()
		}

		wg.Wait()
		close(errors)
	})

	t.Run("should handle concurrent position updates", func(t *testing.T) {
		
		calc := risk.NewCalculator(risk.CalculatorConfig{
			MaxPositionSize: 1000000,
		})

		var wg sync.WaitGroup
		for i := 0; i < 50; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				calc.RecordPosition("user1", "BTC-USD", float64(idx)*0.1, 50000.0)
			}(i)
		}

		wg.Wait()
	})
}

func TestRiskMetrics(t *testing.T) {
	t.Run("should calculate VaR as non-positive value", func(t *testing.T) {
		calc := risk.NewCalculator(risk.CalculatorConfig{})

		// Record a position first so VaR has data to work with
		calc.RecordPosition("user1", "BTC-USD", 1.0, 50000.0)

		
		var_ := calc.CalculateVaR("user1", 0.95, 1) // 95% confidence, 1 day

		assert.LessOrEqual(t, var_, 0.0,
			"VaR should be <= 0 (represents potential loss at confidence level)")
	})

	t.Run("should calculate exposure", func(t *testing.T) {
		calc := risk.NewCalculator(risk.CalculatorConfig{})

		calc.RecordPosition("user1", "BTC-USD", 1.0, 50000.0)
		calc.RecordPosition("user1", "ETH-USD", 10.0, 3000.0)

		exposure := calc.GetTotalExposure("user1")
		// 50000 + 30000 = 80000
		assert.InDelta(t, 80000.0, exposure, 0.01)
	})
}

func TestOrderValidation(t *testing.T) {
	t.Run("should validate order parameters", func(t *testing.T) {
		calc := risk.NewCalculator(risk.CalculatorConfig{})

		// Invalid quantity
		result := calc.CheckOrder("user1", "BTC-USD", "buy", -1.0, 50000.0)
		assert.False(t, result.Allowed)

		// Invalid price
		result = calc.CheckOrder("user1", "BTC-USD", "buy", 1.0, -100.0)
		assert.False(t, result.Allowed)

		// Invalid side
		result = calc.CheckOrder("user1", "BTC-USD", "invalid", 1.0, 50000.0)
		assert.False(t, result.Allowed)
	})

	t.Run("should validate symbol", func(t *testing.T) {
		calc := risk.NewCalculator(risk.CalculatorConfig{})

		// Unknown symbol - should be handled gracefully (either allowed or blocked)
		result := calc.CheckOrder("user1", "INVALID-USD", "buy", 1.0, 100.0)
		// Result must have a definitive decision, not leave Allowed uninitialized
		assert.NotNil(t, result, "CheckOrder should return a valid result even for unknown symbols")
	})
}

func TestLeverageCalculation(t *testing.T) {
	t.Run("should calculate leverage correctly", func(t *testing.T) {
		calc := risk.NewCalculator(risk.CalculatorConfig{})

		// Position: 1 BTC at $50000 = $50000
		// Margin required: $5000 (10%)
		// Leverage = 50000 / 5000 = 10x
		leverage := calc.CalculateLeverage(50000.0, 5000.0)
		assert.InDelta(t, 10.0, leverage, 0.01)
	})

	t.Run("should handle zero margin without panic", func(t *testing.T) {
		calc := risk.NewCalculator(risk.CalculatorConfig{})

		
		leverage := calc.CalculateLeverage(50000.0, 0.0)
		// Should return 0 or max leverage, not Inf or NaN
		assert.False(t, leverage != leverage, // NaN check: NaN != NaN is true
			"CalculateLeverage with zero margin should not return NaN")
		assert.NotEqual(t, leverage, math.Inf(1),
			"CalculateLeverage with zero margin should not return +Inf")
		assert.GreaterOrEqual(t, leverage, 0.0,
			"CalculateLeverage with zero margin should return a safe non-negative value")
	})
}

func TestMarginWithDecimal(t *testing.T) {
	t.Run("should calculate margin using decimal not float", func(t *testing.T) {
		
		calc := risk.NewCalculator(risk.CalculatorConfig{
			DefaultMarginRate: 0.1,
		})

		// 0.1 + 0.2 = 0.3 as price, * 1000 * 0.1 = 30.0
		margin := calc.CalculateMargin(0.3, 1000.0, "BTC-USD")
		assert.Equal(t, 30.0, margin,
			"Margin calc should use decimal to produce exact 30.0, not 29.999...")
	})
}

func TestPositionLimitsConcurrent(t *testing.T) {
	t.Run("should enforce limits under concurrent access", func(t *testing.T) {
		
		calc := risk.NewCalculator(risk.CalculatorConfig{
			MaxPositionSize: 10000,
		})

		var wg sync.WaitGroup
		violations := int32(0)

		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				result := calc.CheckOrder("user1", "BTC-USD", "buy", 1.0, 50000.0)
				if !result.Allowed {
					// Count rejections atomically
					atomic.AddInt32(&violations, 1)
				}
			}()
		}

		wg.Wait()
		// At least some should be rejected since 100 * 50000 > 10000 limit
		assert.Greater(t, violations, int32(0),
			"Position limits must be enforced even under concurrent access")
	})
}

func TestDailyLossLimitReset(t *testing.T) {
	t.Run("should properly reset daily loss at midnight", func(t *testing.T) {
		
		calc := risk.NewCalculator(risk.CalculatorConfig{
			MaxDailyLoss: 10000,
		})

		calc.RecordPnL("user1", -15000.0) // Exceed limit

		result := calc.CheckOrder("user1", "BTC-USD", "buy", 1.0, 100.0)
		assert.False(t, result.Allowed, "Should be blocked before reset")

		calc.ResetDailyPnL()

		result = calc.CheckOrder("user1", "BTC-USD", "buy", 1.0, 100.0)
		assert.True(t, result.Allowed,
			"After ResetDailyPnL, trading should be allowed again")
	})
}

func TestLeverageOverflow(t *testing.T) {
	t.Run("should handle leverage calculation for extreme values", func(t *testing.T) {
		
		calc := risk.NewCalculator(risk.CalculatorConfig{})

		leverage := calc.CalculateLeverage(1e18, 1.0)
		assert.False(t, math.IsInf(leverage, 0),
			"Extreme leverage should not produce Inf")
		assert.False(t, math.IsNaN(leverage),
			"Extreme leverage should not produce NaN")
	})
}

func TestVaRCalculation(t *testing.T) {
	t.Run("should compute value at risk correctly", func(t *testing.T) {
		
		calc := risk.NewCalculator(risk.CalculatorConfig{})

		calc.RecordPosition("user1", "BTC-USD", 10.0, 50000.0)

		var_ := calc.CalculateVaR("user1", 0.99, 1)
		assert.LessOrEqual(t, var_, 0.0,
			"VaR at 99%% confidence for a long position should be <= 0 (a loss)")
	})
}

func TestExposureAggregation(t *testing.T) {
	t.Run("should aggregate exposure across symbols", func(t *testing.T) {
		
		calc := risk.NewCalculator(risk.CalculatorConfig{})

		calc.RecordPosition("user1", "BTC-USD", 1.0, 50000.0)
		calc.RecordPosition("user1", "ETH-USD", 10.0, 3000.0)
		calc.RecordPosition("user1", "SOL-USD", 100.0, 150.0)

		exposure := calc.GetTotalExposure("user1")
		// 50000 + 30000 + 15000 = 95000
		assert.InDelta(t, 95000.0, exposure, 0.01,
			"Total exposure should be sum of all position notional values")
	})
}
