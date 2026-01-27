package service

import (
	"context"
	"fmt"
	"time"

	"github.com/giakiet05/uit-ai-assistant/backend/internal/model"
	platformgrpc "github.com/giakiet05/uit-ai-assistant/backend/internal/platform/grpc"
	"github.com/giakiet05/uit-ai-assistant/backend/internal/repo"
	"go.mongodb.org/mongo-driver/bson/primitive"
)

// ChatService interface defines chat business logic operations
type ChatService interface {
	Chat(ctx context.Context, userID string, sessionID *string, message string) (*model.ChatMessage, error)
	GetSessionsByUserID(ctx context.Context, userID string, opts *repo.FindOptions) ([]*model.ChatSession, error)
	GetSessionByID(ctx context.Context, userID string, sessionID string) (*model.ChatSession, error)
	GetMessagesBySessionID(ctx context.Context, userID string, sessionID string, limit int) ([]*model.ChatMessage, error)
	DeleteSession(ctx context.Context, userID string, sessionID string) error
	UpdateSessionTitle(ctx context.Context, userID string, sessionID string, title string) (*model.ChatSession, error)
}

type chatService struct {
	sessionRepo    repo.ChatSessionRepo
	messageRepo    repo.ChatMessageRepo
	agentClient    *platformgrpc.AgentClient
	sourceEnricher SourceEnricher
}

// NewChatService creates a new chat service
func NewChatService(
	sessionRepo repo.ChatSessionRepo,
	messageRepo repo.ChatMessageRepo,
	agentClient *platformgrpc.AgentClient,
	sourceEnricher SourceEnricher,
) ChatService {
	return &chatService{
		sessionRepo:    sessionRepo,
		messageRepo:    messageRepo,
		agentClient:    agentClient,
		sourceEnricher: sourceEnricher,
	}
}

// Chat handles a chat request
// It creates/loads session, loads history, calls agent, and saves messages
func (s *chatService) Chat(ctx context.Context, userID string, sessionID *string, message string) (*model.ChatMessage, error) {
	// Step 1: Convert userID string to ObjectID
	userObjectID, err := primitive.ObjectIDFromHex(userID)
	if err != nil {
		return nil, fmt.Errorf("invalid user ID: %w", err)
	}

	// Step 2: Get or create session
	var session *model.ChatSession

	if sessionID != nil && *sessionID != "" {
		// Load existing session
		session, err = s.sessionRepo.GetByID(ctx, *sessionID)
		if err != nil {
			return nil, fmt.Errorf("failed to get session: %w", err)
		}

		// Verify session belongs to user
		if session.UserID != userObjectID {
			return nil, fmt.Errorf("session does not belong to user")
		}
	} else {
		// Create new session
		// Use first 50 chars of message as title
		title := message
		if len(title) > 50 {
			title = title[:50] + "..."
		}

		session = &model.ChatSession{
			UserID: userObjectID,
			Title:  title,
		}

		session, err = s.sessionRepo.Create(ctx, session)
		if err != nil {
			return nil, fmt.Errorf("failed to create session: %w", err)
		}
	}

	// Step 2: Construct thread_id for LangGraph checkpointer
	// Format: "user_id:session_id" (e.g., "507f1f77bcf86cd799439011:507f191e810c19729de860ea")
	threadID := fmt.Sprintf("%s:%s", userID, session.ID.Hex())

	// Step 3: Call agent via gRPC (no history needed - checkpointer manages state)
	startTime := time.Now()
	agentResp, err := s.agentClient.Chat(ctx, message, userID, threadID)
	if err != nil {
		return nil, fmt.Errorf("agent call failed: %w", err)
	}
	latency := time.Since(startTime)

	// Step 4: Save user message
	userMsg := &model.ChatMessage{
		SessionID: session.ID,
		Role:      model.RoleUser,
		Content:   message,
		Metadata:  nil, // No metadata for user messages
	}

	_, err = s.messageRepo.Create(ctx, userMsg)
	if err != nil {
		return nil, fmt.Errorf("failed to save user message: %w", err)
	}

	// Step 5: Save assistant message with metadata
	assistantMsg := &model.ChatMessage{
		SessionID: session.ID,
		Role:      model.RoleAssistant,
		Content:   agentResp.Content,
		Metadata:  s.buildMetadata(agentResp, latency),
	}

	assistantMsg, err = s.messageRepo.Create(ctx, assistantMsg)
	if err != nil {
		return nil, fmt.Errorf("failed to save assistant message: %w", err)
	}

	// Step 6: Update session timestamp
	session.UpdatedAt = time.Now()
	_, err = s.sessionRepo.Update(ctx, session)
	if err != nil {
		// Log error but don't fail the request
		fmt.Printf("failed to update session timestamp: %v\n", err)
	}

	return assistantMsg, nil
}

// buildMetadata converts agent response to MongoDB metadata
func (s *chatService) buildMetadata(resp *platformgrpc.AgentResponse, latency time.Duration) map[string]any {
	metadata := make(map[string]any)

	// Enrich and save sources
	if len(resp.Sources) > 0 {
		enrichedSources, err := s.sourceEnricher.EnrichSources(resp.Sources)
		if err != nil {
			// Log error but don't fail - save raw sources as fallback
			fmt.Printf("failed to enrich sources: %v\n", err)
			// Save raw sources (IDs only)
			rawSources := make([]map[string]any, len(resp.Sources))
			for i, src := range resp.Sources {
				rawSources[i] = map[string]any{
					"doc_id":   src.DocID,
					"node_ids": src.NodeIDs,
				}
			}
			metadata["sources"] = rawSources
		} else {
			// Save enriched sources
			metadata["sources"] = enrichedSources
		}
	}

	// Stats
	if resp.TokensUsed > 0 {
		metadata["tokens_used"] = resp.TokensUsed
	}

	// Latency (from gRPC call time)
	metadata["latency_ms"] = int(latency.Milliseconds())

	// If agent also reported latency, store it separately
	if resp.LatencyMs > 0 {
		metadata["agent_latency_ms"] = resp.LatencyMs
	}

	return metadata
}

// GetSessionsByUserID retrieves all sessions for a user
func (s *chatService) GetSessionsByUserID(ctx context.Context, userID string, opts *repo.FindOptions) ([]*model.ChatSession, error) {
	sessions, err := s.sessionRepo.GetByUserID(ctx, userID, opts)
	if err != nil {
		return nil, fmt.Errorf("failed to get sessions: %w", err)
	}
	return sessions, nil
}

// GetSessionByID retrieves a session by ID
func (s *chatService) GetSessionByID(ctx context.Context, userID string, sessionID string) (*model.ChatSession, error) {
	userObjectID, err := primitive.ObjectIDFromHex(userID)
	if err != nil {
		return nil, fmt.Errorf("invalid user ID: %w", err)
	}

	session, err := s.sessionRepo.GetByID(ctx, sessionID)
	if err != nil {
		return nil, fmt.Errorf("failed to get session: %w", err)
	}

	// Verify ownership
	if session.UserID != userObjectID {
		return nil, fmt.Errorf("session does not belong to user")
	}

	return session, nil
}

// GetMessagesBySessionID retrieves messages for a session
func (s *chatService) GetMessagesBySessionID(ctx context.Context, userID string, sessionID string, limit int) ([]*model.ChatMessage, error) {
	userObjectID, err := primitive.ObjectIDFromHex(userID)
	if err != nil {
		return nil, fmt.Errorf("invalid user ID: %w", err)
	}

	// Verify session ownership
	session, err := s.sessionRepo.GetByID(ctx, sessionID)
	if err != nil {
		return nil, fmt.Errorf("failed to get session: %w", err)
	}

	if session.UserID != userObjectID {
		return nil, fmt.Errorf("session does not belong to user")
	}

	// Get messages
	messages, err := s.messageRepo.GetBySessionID(ctx, sessionID, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to get messages: %w", err)
	}

	// Enrich metadata for all messages (in case old messages have raw sources)
	for _, msg := range messages {
		if msg.Metadata != nil {
			s.enrichMessageMetadata(msg.Metadata)
		}
	}

	return messages, nil
}

// enrichMessageMetadata enriches raw sources in message metadata (in-place)
func (s *chatService) enrichMessageMetadata(metadata map[string]any) {
	// Check if sources exist and are in raw format (array of maps with doc_id, node_ids)
	sourcesRaw, ok := metadata["sources"]
	if !ok || sourcesRaw == nil {
		return
	}

	// Try to detect if sources are already enriched (have pdf_url field)
	sourcesSlice, ok := sourcesRaw.([]interface{})
	if !ok || len(sourcesSlice) == 0 {
		return
	}

	// Check first source to see if it's already enriched
	firstSource, ok := sourcesSlice[0].(map[string]interface{})
	if !ok {
		return
	}

	// If already enriched (has pdf_url or source_url), skip
	if _, hasPdfURL := firstSource["pdf_url"]; hasPdfURL {
		return
	}
	if _, hasSourceURL := firstSource["source_url"]; hasSourceURL {
		return
	}

	// Convert raw sources to ReasoningSource format
	rawSources := make([]platformgrpc.ReasoningSource, 0, len(sourcesSlice))
	for _, srcRaw := range sourcesSlice {
		srcMap, ok := srcRaw.(map[string]interface{})
		if !ok {
			continue
		}

		docID, _ := srcMap["doc_id"].(string)
		nodeIDsRaw, _ := srcMap["node_ids"].([]interface{})
		
		nodeIDs := make([]string, 0, len(nodeIDsRaw))
		for _, nid := range nodeIDsRaw {
			if nidStr, ok := nid.(string); ok {
				nodeIDs = append(nodeIDs, nidStr)
			}
		}

		rawSources = append(rawSources, platformgrpc.ReasoningSource{
			DocID:   docID,
			NodeIDs: nodeIDs,
		})
	}

	// Enrich sources
	enrichedSources, err := s.sourceEnricher.EnrichSources(rawSources)
	if err != nil {
		// If enrichment fails, keep raw sources
		fmt.Printf("failed to enrich sources during message retrieval: %v\n", err)
		return
	}

	// Replace raw sources with enriched sources
	metadata["sources"] = enrichedSources
}

// DeleteSession soft deletes a session
func (s *chatService) DeleteSession(ctx context.Context, userID string, sessionID string) error {
	userObjectID, err := primitive.ObjectIDFromHex(userID)
	if err != nil {
		return fmt.Errorf("invalid user ID: %w", err)
	}

	// Verify ownership
	session, err := s.sessionRepo.GetByID(ctx, sessionID)
	if err != nil {
		return fmt.Errorf("failed to get session: %w", err)
	}

	if session.UserID != userObjectID {
		return fmt.Errorf("session does not belong to user")
	}

	// Soft delete session
	err = s.sessionRepo.Delete(ctx, sessionID)
	if err != nil {
		return fmt.Errorf("failed to delete session: %w", err)
	}

	return nil
}

// UpdateSessionTitle updates the session title
func (s *chatService) UpdateSessionTitle(ctx context.Context, userID string, sessionID string, title string) (*model.ChatSession, error) {
	userObjectID, err := primitive.ObjectIDFromHex(userID)
	if err != nil {
		return nil, fmt.Errorf("invalid user ID: %w", err)
	}

	// Verify ownership
	session, err := s.sessionRepo.GetByID(ctx, sessionID)
	if err != nil {
		return nil, fmt.Errorf("failed to get session: %w", err)
	}

	if session.UserID != userObjectID {
		return nil, fmt.Errorf("session does not belong to user")
	}

	// Update title
	session.Title = title
	session, err = s.sessionRepo.Update(ctx, session)
	if err != nil {
		return nil, fmt.Errorf("failed to update session: %w", err)
	}

	return session, nil
}
