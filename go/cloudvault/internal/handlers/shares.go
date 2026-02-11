package handlers

import (
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/terminal-bench/cloudvault/internal/middleware"
	"github.com/terminal-bench/cloudvault/internal/models"
	"github.com/terminal-bench/cloudvault/internal/repository"
)

// ShareHandler handles share-related requests
type ShareHandler struct {
	repo *repository.FileRepository
}

// NewShareHandler creates a new share handler
func NewShareHandler(repo *repository.FileRepository) *ShareHandler {
	return &ShareHandler{repo: repo}
}

// CreateShareRequest represents a share creation request
type CreateShareRequest struct {
	FileID     uuid.UUID `json:"file_id" binding:"required"`
	ShareType  string    `json:"share_type" binding:"required"`
	Permission string    `json:"permission" binding:"required"`
	Password   string    `json:"password,omitempty"`
	MaxUses    *int      `json:"max_uses,omitempty"`
	ExpiresIn  *int      `json:"expires_in,omitempty"` // seconds
}

// Create creates a new share
func (h *ShareHandler) Create(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	var req CreateShareRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}

	// Check file ownership
	file, err := h.repo.GetByID(c.Request.Context(), req.FileID)
	if err != nil || file == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "file not found"})
		return
	}

	if file.UserID != userID {
		c.JSON(http.StatusForbidden, gin.H{"error": "access denied"})
		return
	}

	// Generate share token
	tokenBytes := make([]byte, 32)
	
	rand.Read(tokenBytes)
	token := hex.EncodeToString(tokenBytes)

	share := &models.Share{
		ID:         uuid.New(),
		FileID:     req.FileID,
		OwnerID:    userID,
		ShareType:  req.ShareType,
		Permission: req.Permission,
		Token:      token,
		MaxUses:    req.MaxUses,
		UseCount:   0,
		CreatedAt:  time.Now(),
		UpdatedAt:  time.Now(),
	}

	// Handle password
	if req.Password != "" {
		
		share.Password = &req.Password
	}

	// Handle expiration
	if req.ExpiresIn != nil {
		expiresAt := time.Now().Add(time.Duration(*req.ExpiresIn) * time.Second)
		share.ExpiresAt = &expiresAt
	}

	// TODO: Save share to database (simplified for now)

	c.JSON(http.StatusCreated, gin.H{
		"id":          share.ID,
		"token":       share.Token,
		"share_url":   "/share/" + share.Token,
		"expires_at":  share.ExpiresAt,
	})
}

// Get retrieves a share by ID or token
func (h *ShareHandler) Get(c *gin.Context) {
	idOrToken := c.Param("id")

	// Try parsing as UUID first
	shareID, err := uuid.Parse(idOrToken)
	if err != nil {
		// Assume it's a token
		h.getByToken(c, idOrToken)
		return
	}

	// Get by ID (requires auth)
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	_ = shareID
	_ = userID

	// TODO: Implement database query
	c.JSON(http.StatusNotFound, gin.H{"error": "share not found"})
}

func (h *ShareHandler) getByToken(c *gin.Context, token string) {
	// Public access via token
	// TODO: Implement database query and access logging

	// Check password if required
	password := c.Query("password")
	_ = password

	
	// Should use subtle.ConstantTimeCompare

	c.JSON(http.StatusNotFound, gin.H{"error": "share not found"})
}

// Delete deletes a share
func (h *ShareHandler) Delete(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	shareID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid share ID"})
		return
	}

	_ = userID
	_ = shareID

	// TODO: Implement delete with ownership check

	c.JSON(http.StatusOK, gin.H{"message": "share deleted"})
}

// Access logs access to a share
func (h *ShareHandler) Access(c *gin.Context) {
	token := c.Param("token")
	_ = token

	// TODO: Implement access logging and file download

	c.JSON(http.StatusNotFound, gin.H{"error": "share not found"})
}
