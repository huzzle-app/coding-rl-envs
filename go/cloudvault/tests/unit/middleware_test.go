package unit

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/terminal-bench/cloudvault/internal/config"
	"github.com/terminal-bench/cloudvault/internal/middleware"
)

func init() {
	gin.SetMode(gin.TestMode)
}

func TestAuthMiddleware(t *testing.T) {
	cfg := &config.Config{
		JWTSecret: "test-secret",
	}

	t.Run("should reject missing auth header", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/", nil)

		authMiddleware := middleware.Auth(cfg)
		authMiddleware(c)

		assert.Equal(t, http.StatusUnauthorized, w.Code)
	})

	t.Run("should reject invalid auth header format", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/", nil)
		c.Request.Header.Set("Authorization", "InvalidFormat token123")

		authMiddleware := middleware.Auth(cfg)
		authMiddleware(c)

		assert.Equal(t, http.StatusUnauthorized, w.Code)
	})

	t.Run("should reject invalid token", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/", nil)
		c.Request.Header.Set("Authorization", "Bearer invalid.token.here")

		authMiddleware := middleware.Auth(cfg)
		authMiddleware(c)

		assert.Equal(t, http.StatusUnauthorized, w.Code)
	})

	t.Run("should accept valid token", func(t *testing.T) {
		userID := uuid.New()
		token := jwt.NewWithClaims(jwt.SigningMethodHS256, &middleware.Claims{
			UserID: userID,
			Email:  "test@example.com",
			RegisteredClaims: jwt.RegisteredClaims{
				ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour)),
			},
		})
		tokenString, _ := token.SignedString([]byte(cfg.JWTSecret))

		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/", nil)
		c.Request.Header.Set("Authorization", "Bearer "+tokenString)

		authMiddleware := middleware.Auth(cfg)
		authMiddleware(c)

		// Should not be aborted (continues to next handler)
		assert.False(t, c.IsAborted())
	})

	t.Run("should reject expired token", func(t *testing.T) {
		userID := uuid.New()
		token := jwt.NewWithClaims(jwt.SigningMethodHS256, &middleware.Claims{
			UserID: userID,
			Email:  "test@example.com",
			RegisteredClaims: jwt.RegisteredClaims{
				ExpiresAt: jwt.NewNumericDate(time.Now().Add(-time.Hour)),
			},
		})
		tokenString, _ := token.SignedString([]byte(cfg.JWTSecret))

		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/", nil)
		c.Request.Header.Set("Authorization", "Bearer "+tokenString)

		authMiddleware := middleware.Auth(cfg)
		authMiddleware(c)

		assert.Equal(t, http.StatusUnauthorized, w.Code)
	})
}

func TestGetUserID(t *testing.T) {
	t.Run("should return user ID from context", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		userID := uuid.New()
		c.Set("user_id", userID)

		result, err := middleware.GetUserID(c)
		assert.NoError(t, err)
		assert.Equal(t, userID, result)
	})

	t.Run("should return nil UUID if not set", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)

		result, err := middleware.GetUserID(c)
		assert.NoError(t, err)
		assert.Equal(t, uuid.Nil, result)
	})

	t.Run("should panic on wrong type", func(t *testing.T) {
		
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("user_id", "not-a-uuid")

		assert.Panics(t, func() {
			middleware.GetUserID(c)
		})
	})
}

func TestGetEmail(t *testing.T) {
	t.Run("should return email from context", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Set("email", "test@example.com")

		result := middleware.GetEmail(c)
		assert.Equal(t, "test@example.com", result)
	})

	t.Run("should panic if not set", func(t *testing.T) {
		
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)

		assert.Panics(t, func() {
			middleware.GetEmail(c)
		})
	})
}

func TestOptionalAuthMiddleware(t *testing.T) {
	cfg := &config.Config{
		JWTSecret: "test-secret",
	}

	t.Run("should allow request without auth", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/", nil)

		authMiddleware := middleware.OptionalAuth(cfg)
		authMiddleware(c)

		assert.False(t, c.IsAborted())
	})

	t.Run("should set user if valid token provided", func(t *testing.T) {
		userID := uuid.New()
		token := jwt.NewWithClaims(jwt.SigningMethodHS256, &middleware.Claims{
			UserID: userID,
			Email:  "test@example.com",
			RegisteredClaims: jwt.RegisteredClaims{
				ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour)),
			},
		})
		tokenString, _ := token.SignedString([]byte(cfg.JWTSecret))

		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/", nil)
		c.Request.Header.Set("Authorization", "Bearer "+tokenString)

		authMiddleware := middleware.OptionalAuth(cfg)
		authMiddleware(c)

		assert.False(t, c.IsAborted())
		result, _ := middleware.GetUserID(c)
		assert.Equal(t, userID, result)
	})
}

func TestRequireRoleMiddleware(t *testing.T) {
	t.Run("should reject if role not set", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/", nil)

		roleMiddleware := middleware.RequireRole("admin")
		roleMiddleware(c)

		assert.Equal(t, http.StatusForbidden, w.Code)
	})

	t.Run("should accept if role matches", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/", nil)
		c.Set("role", "admin")

		roleMiddleware := middleware.RequireRole("admin", "superadmin")
		roleMiddleware(c)

		assert.False(t, c.IsAborted())
	})

	t.Run("should reject if role doesn't match", func(t *testing.T) {
		w := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(w)
		c.Request = httptest.NewRequest("GET", "/", nil)
		c.Set("role", "user")

		roleMiddleware := middleware.RequireRole("admin")
		roleMiddleware(c)

		assert.Equal(t, http.StatusForbidden, w.Code)
	})
}
