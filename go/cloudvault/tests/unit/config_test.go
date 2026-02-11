package unit

import (
	"os"
	"sync"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/terminal-bench/cloudvault/internal/config"
)

func TestConfigLoading(t *testing.T) {
	t.Run("should load config with defaults", func(t *testing.T) {
		cfg, err := config.Load()
		assert.NoError(t, err)
		assert.NotNil(t, cfg)
		assert.Equal(t, "8080", cfg.Port)
	})

	t.Run("should use environment variables", func(t *testing.T) {
		os.Setenv("PORT", "9000")
		defer os.Unsetenv("PORT")

		
		cfg := config.Get()
		assert.NotNil(t, cfg)
	})
}

func TestConfigEnvParsing(t *testing.T) {
	t.Run("should parse MAX_FILE_SIZE correctly", func(t *testing.T) {
		os.Setenv("MAX_FILE_SIZE", "52428800") // 50MB
		defer os.Unsetenv("MAX_FILE_SIZE")

		cfg, err := config.Load()
		require.NoError(t, err)
		
		assert.Equal(t, int64(52428800), cfg.MaxFileSize)
	})

	t.Run("should parse RATE_LIMIT_RPS correctly", func(t *testing.T) {
		os.Setenv("RATE_LIMIT_RPS", "200")
		defer os.Unsetenv("RATE_LIMIT_RPS")

		cfg, err := config.Load()
		require.NoError(t, err)
		
		assert.Equal(t, 200, cfg.RateLimitRPS)
	})

	t.Run("should fail gracefully on invalid MAX_FILE_SIZE", func(t *testing.T) {
		os.Setenv("MAX_FILE_SIZE", "not-a-number")
		defer os.Unsetenv("MAX_FILE_SIZE")

		cfg, err := config.Load()
		
		if err == nil {
			assert.NotEqual(t, int64(0), cfg.MaxFileSize,
				"invalid MAX_FILE_SIZE should not result in 0, should use default or return error")
		}
	})

	t.Run("should parse CHUNK_SIZE with Atoi", func(t *testing.T) {
		os.Setenv("CHUNK_SIZE", "10485760") // 10MB
		defer os.Unsetenv("CHUNK_SIZE")

		cfg, err := config.Load()
		require.NoError(t, err)
		
		assert.Equal(t, int64(10485760), cfg.ChunkSize,
			"CHUNK_SIZE should be parsed as int64, not int (Atoi overflow risk)")
	})

	t.Run("should parse DEBUG as boolean", func(t *testing.T) {
		os.Setenv("DEBUG", "true")
		defer os.Unsetenv("DEBUG")

		cfg, err := config.Load()
		require.NoError(t, err)
		assert.True(t, cfg.Debug, "DEBUG=true should result in Debug=true")
	})

	t.Run("should accept DEBUG=1 as true", func(t *testing.T) {
		os.Setenv("DEBUG", "1")
		defer os.Unsetenv("DEBUG")

		cfg, err := config.Load()
		require.NoError(t, err)
		
		assert.True(t, cfg.Debug,
			"DEBUG=1 should be interpreted as true (common convention)")
	})
}

func TestConfigValidation(t *testing.T) {
	t.Run("should validate required fields", func(t *testing.T) {
		
		os.Setenv("ENV", "production")
		os.Setenv("JWT_SECRET", "")
		os.Setenv("ENCRYPTION_KEY", "")
		defer os.Unsetenv("ENV")
		defer os.Unsetenv("JWT_SECRET")
		defer os.Unsetenv("ENCRYPTION_KEY")

		cfg, err := config.Load()
		// In production mode, empty secrets should be rejected
		if err == nil && cfg != nil {
			assert.NotEmpty(t, cfg.JWTSecret,
				"JWTSecret should not be empty in production mode")
			assert.NotEmpty(t, cfg.EncryptionKey,
				"EncryptionKey should not be empty in production mode")
		}
	})

	t.Run("should validate JWT secret strength", func(t *testing.T) {
		os.Setenv("JWT_SECRET", "abc") // too short
		defer os.Unsetenv("JWT_SECRET")

		cfg, err := config.Load()
		
		if err == nil && cfg != nil {
			assert.GreaterOrEqual(t, len(cfg.JWTSecret), 16,
				"JWT secret should be at least 16 characters for security")
		}
	})

	t.Run("should parse ALLOWED_ORIGINS correctly", func(t *testing.T) {
		os.Setenv("ALLOWED_ORIGINS", "http://localhost,http://example.com")
		defer os.Unsetenv("ALLOWED_ORIGINS")

		cfg, err := config.Load()
		require.NoError(t, err)
		
		assert.GreaterOrEqual(t, len(cfg.AllowedOrigins), 2,
			"ALLOWED_ORIGINS should be split by comma into multiple entries")
	})
}

func TestConfigGet(t *testing.T) {
	t.Run("should return config after Load", func(t *testing.T) {
		_, err := config.Load()
		require.NoError(t, err)
		cfg := config.Get()
		assert.NotNil(t, cfg, "Get() should return non-nil config after Load()")
	})

	t.Run("should return same instance on multiple Get calls", func(t *testing.T) {
		cfg1 := config.Get()
		cfg2 := config.Get()
		assert.Equal(t, cfg1, cfg2)
	})
}

func TestConfigRaceCondition(t *testing.T) {
	t.Run("should handle concurrent access safely", func(t *testing.T) {
		
		// mu sync.Mutex is declared but never used
		var wg sync.WaitGroup
		errors := make(chan error, 20)

		for i := 0; i < 20; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				cfg := config.Get()
				if cfg == nil {
					errors <- assert.AnError
					return
				}
				// Access fields concurrently to trigger race
				_ = cfg.Port
				_ = cfg.Debug
				_ = cfg.MaxFileSize
			}()
		}

		wg.Wait()
		close(errors)

		for err := range errors {
			t.Errorf("concurrent config access failed: %v", err)
		}
	})
}
