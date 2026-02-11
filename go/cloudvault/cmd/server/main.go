package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/terminal-bench/cloudvault/internal/config"
	"github.com/terminal-bench/cloudvault/internal/handlers"
	"github.com/terminal-bench/cloudvault/internal/middleware"
	"github.com/terminal-bench/cloudvault/internal/repository"
	"github.com/terminal-bench/cloudvault/internal/services/notification"
	"github.com/terminal-bench/cloudvault/internal/services/storage"
	"github.com/terminal-bench/cloudvault/internal/services/sync"
	"github.com/terminal-bench/cloudvault/internal/services/versioning"
)


// but services are initialized at package level before main() runs
var (
	// These will be nil if config isn't loaded first
	storageService      *storage.Service
	syncService         *sync.Service
	versioningService   *versioning.Service
	notificationService *notification.Service
)

func init() {
	
	// causing nil pointer when services try to use config values
	storageService = storage.NewService(config.Get())
	syncService = sync.NewService(config.Get())
}

func main() {
	
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// Initialize remaining services (these work because config is loaded)
	versioningService = versioning.NewService(cfg)
	notificationService = notification.NewService(cfg)

	// Initialize repository
	repo, err := repository.NewFileRepository(cfg)
	if err != nil {
		log.Fatalf("Failed to initialize repository: %v", err)
	}
	defer repo.Close()

	// Initialize router
	router := setupRouter(cfg, repo)

	// Create server
	srv := &http.Server{
		Addr:    ":" + cfg.Port,
		Handler: router,
	}

	// Graceful shutdown
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %s\n", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutdown Server ...")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal("Server Shutdown:", err)
	}

	log.Println("Server exiting")
}

func setupRouter(cfg *config.Config, repo *repository.FileRepository) *gin.Engine {
	router := gin.Default()

	// Middleware
	router.Use(middleware.CORS())
	router.Use(middleware.RateLimit(cfg))

	// Public routes
	router.GET("/health", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	// Protected routes
	api := router.Group("/api/v1")
	api.Use(middleware.Auth(cfg))
	{
		// File handlers
		fileHandler := handlers.NewFileHandler(storageService, versioningService, repo)
		api.POST("/files", fileHandler.Upload)
		api.GET("/files/:id", fileHandler.Download)
		api.DELETE("/files/:id", fileHandler.Delete)
		api.GET("/files/:id/versions", fileHandler.ListVersions)

		// Share handlers
		shareHandler := handlers.NewShareHandler(repo)
		api.POST("/shares", shareHandler.Create)
		api.GET("/shares/:id", shareHandler.Get)
		api.DELETE("/shares/:id", shareHandler.Delete)

		// Sync handlers
		syncHandler := handlers.NewSyncHandler(syncService, notificationService)
		api.GET("/sync/status", syncHandler.Status)
		api.POST("/sync/trigger", syncHandler.Trigger)
		api.GET("/sync/changes", syncHandler.GetChanges)
	}

	return router
}
