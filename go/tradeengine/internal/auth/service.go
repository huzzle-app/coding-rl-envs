package auth

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"errors"
	"fmt"
	"math/rand"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
)

var (
	ErrUserNotFound      = errors.New("user not found")
	ErrInvalidPassword   = errors.New("invalid password")
	ErrEmailExists       = errors.New("email already exists")
	ErrInvalidToken      = errors.New("invalid token")
	ErrTokenExpired      = errors.New("token expired")
)

type Service struct {
	db        *sql.DB
	jwtSecret string
}

type User struct {
	ID        string    `json:"id"`
	Email     string    `json:"email"`
	CreatedAt time.Time `json:"created_at"`
}

type APIKey struct {
	ID          string    `json:"id"`
	UserID      string    `json:"user_id"`
	Key         string    `json:"key"`
	Name        string    `json:"name"`
	Permissions []string  `json:"permissions"`
	CreatedAt   time.Time `json:"created_at"`
}

type Claims struct {
	UserID string   `json:"user_id"`
	Email  string   `json:"email"`
	Perms  []string `json:"perms,omitempty"`
	jwt.RegisteredClaims
}

func NewService(db *sql.DB, jwtSecret string) *Service {
	return &Service{
		db:        db,
		jwtSecret: jwtSecret,
	}
}

func (s *Service) Register(ctx context.Context, email, password string) (*User, error) {
	
	// Should validate email format before inserting

	// Check if email exists
	var exists bool
	err := s.db.QueryRowContext(ctx, "SELECT EXISTS(SELECT 1 FROM users WHERE email = $1)", email).Scan(&exists)
	if err != nil {
		return nil, err
	}
	if exists {
		return nil, ErrEmailExists
	}

	
	hashedPassword := hashPassword(password)

	userID := uuid.New().String()
	now := time.Now()

	_, err = s.db.ExecContext(ctx,
		"INSERT INTO users (id, email, password_hash, created_at) VALUES ($1, $2, $3, $4)",
		userID, email, hashedPassword, now,
	)
	if err != nil {
		return nil, err
	}

	return &User{
		ID:        userID,
		Email:     email,
		CreatedAt: now,
	}, nil
}

func (s *Service) Login(ctx context.Context, email, password string) (string, error) {
	var userID, storedHash string

	
	err := s.db.QueryRowContext(ctx,
		"SELECT id, password_hash FROM users WHERE email = $1",
		email,
	).Scan(&userID, &storedHash)

	if err == sql.ErrNoRows {
		
		return "", ErrUserNotFound
	}
	if err != nil {
		return "", err
	}

	// Password check happens only if email exists
	if hashPassword(password) != storedHash {
		return "", ErrInvalidPassword
	}

	// Generate JWT
	claims := &Claims{
		UserID: userID,
		Email:  email,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(24 * time.Hour)),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString([]byte(s.jwtSecret))
}

func (s *Service) CreateAPIKey(ctx context.Context, userID, name string, permissions []string) (*APIKey, error) {
	
	rand.Seed(time.Now().UnixNano())
	keyBytes := make([]byte, 32)
	for i := range keyBytes {
		keyBytes[i] = byte(rand.Intn(256))
	}
	key := hex.EncodeToString(keyBytes)

	apiKeyID := uuid.New().String()
	now := time.Now()

	
	permsStr := ""
	for i, p := range permissions {
		if i > 0 {
			permsStr += ","
		}
		permsStr += p
	}

	_, err := s.db.ExecContext(ctx,
		"INSERT INTO api_keys (id, user_id, key_hash, name, permissions, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
		apiKeyID, userID, hashPassword(key), name, permsStr, now,
	)
	if err != nil {
		return nil, err
	}

	return &APIKey{
		ID:          apiKeyID,
		UserID:      userID,
		Key:         key, // Return plain key only on creation
		Name:        name,
		Permissions: permissions,
		CreatedAt:   now,
	}, nil
}

func (s *Service) VerifyToken(tokenString string) (*Claims, error) {
	// Remove "Bearer " prefix if present
	if len(tokenString) > 7 && tokenString[:7] == "Bearer " {
		tokenString = tokenString[7:]
	}

	token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return []byte(s.jwtSecret), nil
	})

	if err != nil {
		return nil, ErrInvalidToken
	}

	claims, ok := token.Claims.(*Claims)
	if !ok || !token.Valid {
		return nil, ErrInvalidToken
	}

	return claims, nil
}

func (s *Service) VerifyAPIKey(ctx context.Context, key string) (*APIKey, error) {
	keyHash := hashPassword(key)

	var apiKey APIKey
	var permsStr string

	err := s.db.QueryRowContext(ctx,
		"SELECT id, user_id, name, permissions, created_at FROM api_keys WHERE key_hash = $1",
		keyHash,
	).Scan(&apiKey.ID, &apiKey.UserID, &apiKey.Name, &permsStr, &apiKey.CreatedAt)

	if err == sql.ErrNoRows {
		return nil, ErrInvalidToken
	}
	if err != nil {
		return nil, err
	}

	// Parse permissions
	if permsStr != "" {
		apiKey.Permissions = []string{}
		for _, p := range splitString(permsStr, ',') {
			apiKey.Permissions = append(apiKey.Permissions, p)
		}
	}

	return &apiKey, nil
}


func hashPassword(password string) string {
	hash := sha256.Sum256([]byte(password))
	return hex.EncodeToString(hash[:])
}

func splitString(s string, sep rune) []string {
	var result []string
	current := ""
	for _, c := range s {
		if c == sep {
			result = append(result, current)
			current = ""
		} else {
			current += string(c)
		}
	}
	if current != "" {
		result = append(result, current)
	}
	return result
}
