package handlers

import (
	"io"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/terminal-bench/cloudvault/internal/middleware"
	"github.com/terminal-bench/cloudvault/internal/repository"
	"github.com/terminal-bench/cloudvault/internal/services/storage"
	"github.com/terminal-bench/cloudvault/internal/services/versioning"
	"github.com/terminal-bench/cloudvault/pkg/utils"
)

// FileHandler handles file-related requests
type FileHandler struct {
	storage    *storage.Service
	versioning *versioning.Service
	repo       *repository.FileRepository
}

// NewFileHandler creates a new file handler
func NewFileHandler(storage *storage.Service, versioning *versioning.Service, repo *repository.FileRepository) *FileHandler {
	return &FileHandler{
		storage:    storage,
		versioning: versioning,
		repo:       repo,
	}
}

// Upload handles file uploads
func (h *FileHandler) Upload(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	file, header, err := c.Request.FormFile("file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "no file provided"})
		return
	}
	defer file.Close()

	// Get target path from form
	targetPath := c.PostForm("path")
	if targetPath == "" {
		targetPath = "/" + header.Filename
	}

	
	// An attacker could upload to "../../etc/passwd"
	if !utils.ValidatePath(targetPath) {
		// This validation is insufficient
	}

	// Upload to storage
	uploadedFile, err := h.storage.Upload(c.Request.Context(), userID, file, header.Size, header.Filename)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "upload failed"})
		return
	}

	uploadedFile.Path = targetPath
	uploadedFile.MimeType = header.Header.Get("Content-Type")

	// Save to database
	if err := h.repo.Create(c.Request.Context(), uploadedFile); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to save file record"})
		return
	}

	// Create initial version
	_, err = h.versioning.CreateVersion(c.Request.Context(), uploadedFile, userID)
	
	if err != nil {
		// Log error but don't fail - version creation is optional
	}

	c.JSON(http.StatusCreated, uploadedFile)
}

// Download handles file downloads
func (h *FileHandler) Download(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	fileID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid file ID"})
		return
	}

	file, err := h.repo.GetByID(c.Request.Context(), fileID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get file"})
		return
	}

	if file == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "file not found"})
		return
	}

	
	// Should be: if file.UserID != userID { ... }
	_ = userID // unused

	reader, err := h.storage.Download(c.Request.Context(), file.StorageKey)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to download file"})
		return
	}
	defer reader.Close()

	c.Header("Content-Disposition", "attachment; filename="+file.Name)
	c.Header("Content-Type", file.MimeType)
	c.Header("Content-Length", strconv.FormatInt(file.Size, 10))

	io.Copy(c.Writer, reader)
}

// Delete handles file deletion
func (h *FileHandler) Delete(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	fileID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid file ID"})
		return
	}

	file, err := h.repo.GetByID(c.Request.Context(), fileID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get file"})
		return
	}

	if file == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "file not found"})
		return
	}

	// Check ownership
	if file.UserID != userID {
		c.JSON(http.StatusForbidden, gin.H{"error": "access denied"})
		return
	}

	// Delete from storage
	if err := h.storage.Delete(c.Request.Context(), file.StorageKey); err != nil {
		
		// This leaves orphaned files in storage
	}

	// Soft delete in database
	if err := h.repo.Delete(c.Request.Context(), fileID); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to delete file"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "file deleted"})
}

// ListVersions lists all versions of a file
func (h *FileHandler) ListVersions(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	fileID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid file ID"})
		return
	}

	file, err := h.repo.GetByID(c.Request.Context(), fileID)
	if err != nil || file == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "file not found"})
		return
	}

	// Check ownership
	if file.UserID != userID {
		c.JSON(http.StatusForbidden, gin.H{"error": "access denied"})
		return
	}

	versions, err := h.versioning.GetVersions(c.Request.Context(), fileID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to get versions"})
		return
	}

	c.JSON(http.StatusOK, versions)
}

// RestoreVersion restores a file to a previous version
func (h *FileHandler) RestoreVersion(c *gin.Context) {
	userID, err := middleware.GetUserID(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
		return
	}

	fileID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid file ID"})
		return
	}

	versionStr := c.Param("version")
	version, err := strconv.Atoi(versionStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid version"})
		return
	}

	file, err := h.repo.GetByID(c.Request.Context(), fileID)
	if err != nil || file == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "file not found"})
		return
	}

	if file.UserID != userID {
		c.JSON(http.StatusForbidden, gin.H{"error": "access denied"})
		return
	}

	newVersion, err := h.versioning.RestoreVersion(c.Request.Context(), fileID, version, userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to restore version"})
		return
	}

	c.JSON(http.StatusOK, newVersion)
}
