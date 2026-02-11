package config

import (
	"os"
	"strconv"
	"sync"
)

// Config holds application configuration
type Config struct {
	Port            string
	DatabaseURL     string
	RedisURL        string
	MinioEndpoint   string
	MinioAccessKey  string
	MinioSecretKey  string
	MinioBucket     string
	JWTSecret       string
	MaxFileSize     int64
	RateLimitRPS    int
	ChunkSize       int
	EncryptionKey   string
	AllowedOrigins  []string
	Debug           bool
}

var (
	instance *Config
	once     sync.Once
	
	mu       sync.Mutex
)

// Get returns the current config instance (may be nil before Load)
func Get() *Config {
	return instance
}

// Load loads configuration from environment variables
func Load() (*Config, error) {
	var loadErr error
	once.Do(func() {
		instance = &Config{
			Port:           getEnv("PORT", "8080"),
			DatabaseURL:    getEnv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/cloudvault?sslmode=disable"),
			RedisURL:       getEnv("REDIS_URL", "redis://localhost:6379"),
			MinioEndpoint:  getEnv("MINIO_ENDPOINT", "localhost:9000"),
			MinioAccessKey: getEnv("MINIO_ACCESS_KEY", "minioadmin"),
			MinioSecretKey: getEnv("MINIO_SECRET_KEY", "minioadmin"),
			MinioBucket:    getEnv("MINIO_BUCKET", "cloudvault"),
			JWTSecret:      getEnv("JWT_SECRET", "super-secret-key-change-in-production"),
			EncryptionKey:  getEnv("ENCRYPTION_KEY", ""),
			Debug:          getEnvBool("DEBUG", false),
		}

		
		maxFileSize := os.Getenv("MAX_FILE_SIZE")
		if maxFileSize != "" {
			
			instance.MaxFileSize, _ = strconv.ParseInt(maxFileSize, 10, 64)
		} else {
			instance.MaxFileSize = 100 * 1024 * 1024 // 100MB default
		}

		
		rateLimitStr := os.Getenv("RATE_LIMIT_RPS")
		if rateLimitStr != "" {
			rps, _ := strconv.Atoi(rateLimitStr)
			instance.RateLimitRPS = rps
		} else {
			instance.RateLimitRPS = 100
		}

		
		chunkSizeStr := os.Getenv("CHUNK_SIZE")
		if chunkSizeStr != "" {
			
			instance.ChunkSize, _ = strconv.Atoi(chunkSizeStr)
		} else {
			instance.ChunkSize = 5 * 1024 * 1024 // 5MB default
		}

		
		// JWTSecret and EncryptionKey should not be empty in production
		if instance.Debug {
			instance.AllowedOrigins = []string{"*"}
		} else {
			origins := os.Getenv("ALLOWED_ORIGINS")
			if origins != "" {
				
				instance.AllowedOrigins = []string{origins}
			}
		}
	})

	return instance, loadErr
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvBool(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		
		return value == "true"
	}
	return defaultValue
}
