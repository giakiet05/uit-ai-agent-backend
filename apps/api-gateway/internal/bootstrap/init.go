package bootstrap

import (
	"log"

	"github.com/giakiet05/uit-ai-assistant/backend/internal/auth"
	"github.com/giakiet05/uit-ai-assistant/backend/internal/config"
	"github.com/giakiet05/uit-ai-assistant/backend/internal/controller"
	"github.com/giakiet05/uit-ai-assistant/backend/internal/middleware"
	"github.com/giakiet05/uit-ai-assistant/backend/internal/platform/bus"
	"github.com/giakiet05/uit-ai-assistant/backend/internal/platform/email"
	"github.com/giakiet05/uit-ai-assistant/backend/internal/platform/gemini"
	platformgrpc "github.com/giakiet05/uit-ai-assistant/backend/internal/platform/grpc"
	"github.com/giakiet05/uit-ai-assistant/backend/internal/platform/ws"
	"github.com/giakiet05/uit-ai-assistant/backend/internal/repo"
	"github.com/giakiet05/uit-ai-assistant/backend/internal/route"
	"github.com/giakiet05/uit-ai-assistant/backend/internal/service"
	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"
	"go.mongodb.org/mongo-driver/mongo"
)

type Repos struct {
	repo.UserRepo
	repo.NotificationRepo
	repo.EmailVerificationRepo
	repo.ChatSessionRepo
	repo.ChatMessageRepo
}

type Services struct {
	service.AuthService
	service.UserService
	service.NotificationService
	service.AdminUserService
	service.ChatService
}

type Controllers struct {
	controller.AuthController
	controller.UserController
	controller.NotificationController
	controller.WebSocketController
	controller.AdminUserController
	controller.ChatController
	controller.CookieController
	controller.FileController
}

func initRepos(client *mongo.Client, db *mongo.Database) *Repos {
	return &Repos{
		UserRepo:              repo.NewUserRepo(db),
		NotificationRepo:      repo.NewNotificationRepo(db),
		EmailVerificationRepo: repo.NewEmailVerificationRepo(db),
		ChatSessionRepo:       repo.NewChatSessionRepo(db),
		ChatMessageRepo:       repo.NewChatMessageRepo(db),
	}
}

func initServices(repos *Repos, redisClient *redis.Client, emailSender email.Sender, eventBus bus.EventBus, geminiClient *gemini.GeminiClient, agentClient *platformgrpc.AgentClient) *Services {
	// Initialize source enricher
	sourceEnricher := service.NewSourceEnricher(config.Cfg.DataDir, config.Cfg.BaseURL)

	return &Services{
		AuthService:         service.NewAuthService(repos.UserRepo, repos.EmailVerificationRepo, emailSender, redisClient),
		UserService:         service.NewUserService(repos.UserRepo, eventBus, redisClient),
		NotificationService: service.NewNotificationService(repos.NotificationRepo, repos.UserRepo, eventBus, redisClient),
		ChatService:         service.NewChatService(repos.ChatSessionRepo, repos.ChatMessageRepo, agentClient, sourceEnricher),
	}
}

func initControllers(services *Services, wsHub *ws.Hub, redisClient *redis.Client) *Controllers {
	return &Controllers{
		AuthController:         *controller.NewAuthController(services.AuthService),
		UserController:         *controller.NewUserController(services.UserService),
		NotificationController: *controller.NewNotificationController(services.NotificationService),
		WebSocketController:    *controller.NewWebSocketController(wsHub),
		AdminUserController:    *controller.NewAdminUserController(services.AdminUserService),
		ChatController:         *controller.NewChatController(services.ChatService),
		CookieController:       *controller.NewCookieController(redisClient),
		FileController:         *controller.NewFileController(config.Cfg.DataDir),
	}
}

func initRoutes(controllers *Controllers, r *gin.Engine) {
	r.GET("/ping", func(c *gin.Context) {
		c.JSON(200, gin.H{"message": "pong"})
	})

	api := r.Group("/api/v1")
	api.GET("/", func(c *gin.Context) {
		c.JSON(200, gin.H{"message": "Welcome to LKForum API!"})
	})

	route.RegisterAuthRoutes(api, &controllers.AuthController, &controllers.UserController)
	route.RegisterUserRoutes(api, &controllers.UserController)
	route.RegisterNotificationRoutes(api, &controllers.NotificationController)
	route.RegisterWebSocketRoutes(api, &controllers.WebSocketController)
	route.RegisterAdminUserRoutes(api, &controllers.AdminUserController)
	route.RegisterChatRoutes(api, &controllers.ChatController)
	route.RegisterCookieRoutes(api, &controllers.CookieController)
	route.RegisterFileRoutes(api, &controllers.FileController)
}

func Init() (*gin.Engine, error) {
	config.LoadConfig()
	auth.InitGoogleOAuthConfig()

	redisClient := config.NewRedisClient()

	if err := InitializeTokenService(redisClient); err != nil {
		log.Printf("Warning: Token invalidation service not available: %v\n", err)
	}

	client := config.NewMongoClient()
	db := client.Database(config.Cfg.DBName)
	router := gin.Default()

	router.Use(func(c *gin.Context) {
		origin := c.Request.Header.Get("Origin")

		// Allow FrontendURL and ExtensionOrigin
		allowedOrigins := []string{config.Cfg.FrontendURL}
		if config.Cfg.ExtensionOrigin != "" {
			allowedOrigins = append(allowedOrigins, config.Cfg.ExtensionOrigin)
		}

		// Check if origin is allowed
		for _, allowedOrigin := range allowedOrigins {
			if origin == allowedOrigin {
				c.Writer.Header().Set("Access-Control-Allow-Origin", origin)
				break
			}
		}

		c.Writer.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	})

	eventBus := bus.NewEventBus()
	wsHub := ws.NewHub(eventBus)
	emailSender := email.NewSMTPSender()

	// Initialize Gemini client for content moderation
	geminiClient, err := gemini.NewGeminiClient(&config.Cfg.Gemini)
	if err != nil {
		log.Printf("Warning: Gemini client initialization failed: %v. Content moderation will be disabled.", err)
	}

	// Initialize Agent gRPC client
	agentClient, err := platformgrpc.NewAgentClient(config.Cfg.AgentGRPCAddr)
	if err != nil {
		log.Fatalf("Failed to connect to Agent gRPC server: %v", err)
	}
	log.Printf("Connected to Agent gRPC server at %s", config.Cfg.AgentGRPCAddr)

	repos := initRepos(client, db)
	services := initServices(repos, redisClient, emailSender, eventBus, geminiClient, agentClient)
	controllers := initControllers(services, wsHub, redisClient)

	// Inject userRepo into middleware for settings caching
	middleware.SetUserRepo(repos.UserRepo)

	initRoutes(controllers, router)

	// Start background services
	go wsHub.Start()
	services.NotificationService.Start()

	return router, nil
}
