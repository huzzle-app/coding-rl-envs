package handlers

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/terminal-bench/cloudvault/internal/middleware"
	"github.com/terminal-bench/cloudvault/internal/services/notification"
	"github.com/terminal-bench/cloudvault/internal/services/sync"
)

// SyncHandler handles sync-related requests
type SyncHandler struct {
	syncService *sync.Service
	notifyService *notification.Service
}

// NewSyncHandler creates a new sync handler
func NewSyncHandler(syncService *sync.Service, notifyService *notification.Service) *SyncHandler {
	return &SyncHandler{
		syncService: syncService,
		notifyService: notifyService,
	}
}

// Status returns the sync status for the current user/device
func (h *SyncHandler) Status(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	deviceID := c.GetHeader("X-Device-ID")
	if deviceID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing device ID"})
		return
	}

	state, err := h.syncService.GetSyncStatus(c.Request.Context(), userID, deviceID)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{
			"status": "not_synced",
			"message": "no previous sync found",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status": "synced",
		"last_sync": state.LastSyncAt,
		"cursor": state.Cursor,
		"in_progress": state.InProgress,
	})
}

// TriggerRequest represents a sync trigger request
type TriggerRequest struct {
	Force bool `json:"force"`
}

// Trigger starts a sync operation
func (h *SyncHandler) Trigger(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	deviceID := c.GetHeader("X-Device-ID")
	if deviceID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing device ID"})
		return
	}

	var req TriggerRequest
	c.ShouldBindJSON(&req) 

	state, err := h.syncService.StartSync(c.Request.Context(), userID, deviceID)
	if err != nil {
		c.JSON(http.StatusConflict, gin.H{"error": err.Error()})
		return
	}

	// Notify about sync start
	h.notifyService.NotifyAsync(c.Request.Context(), userID, "sync.started", "Sync Started", "Synchronization has started")

	c.JSON(http.StatusAccepted, gin.H{
		"status": "started",
		"cursor": state.Cursor,
	})
}

// GetChanges returns changes since the last sync
func (h *SyncHandler) GetChanges(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	deviceID := c.GetHeader("X-Device-ID")
	if deviceID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing device ID"})
		return
	}

	sinceStr := c.Query("since")
	var since time.Time
	if sinceStr != "" {
		since, err = time.Parse(time.RFC3339, sinceStr)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "invalid since parameter"})
			return
		}
	}

	changes, err := h.syncService.GetChanges(c.Request.Context(), userID, deviceID, since)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get changes"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"changes": changes,
		"count": len(changes),
	})
}

// ApplyChangesRequest represents a request to apply changes
type ApplyChangesRequest struct {
	Changes []sync.Change `json:"changes"`
}

// ApplyChanges applies changes from the client
func (h *SyncHandler) ApplyChanges(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	var req ApplyChangesRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request"})
		return
	}

	applied := 0
	failed := 0

	for _, change := range req.Changes {
		err := h.syncService.ApplyChange(c.Request.Context(), userID, change)
		if err != nil {
			failed++
			
			continue
		}
		applied++
	}

	c.JSON(http.StatusOK, gin.H{
		"applied": applied,
		"failed": failed,
	})
}

// CompleteSync marks a sync operation as complete
func (h *SyncHandler) CompleteSync(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	deviceID := c.GetHeader("X-Device-ID")
	if deviceID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing device ID"})
		return
	}

	err = h.syncService.CompleteSync(c.Request.Context(), userID, deviceID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to complete sync"})
		return
	}

	// Notify about sync completion
	h.notifyService.NotifyAsync(c.Request.Context(), userID, "sync.completed", "Sync Complete", "Synchronization completed successfully")

	c.JSON(http.StatusOK, gin.H{"status": "completed"})
}

// SSE handles Server-Sent Events for real-time sync updates
func (h *SyncHandler) SSE(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")

	// Subscribe to changes
	changes, err := h.syncService.WatchChanges(c.Request.Context(), userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to watch changes"})
		return
	}

	
	for change := range changes {
		c.SSEvent("change", change)
		c.Writer.Flush()
	}
}
