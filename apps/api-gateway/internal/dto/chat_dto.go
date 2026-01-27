package dto

import (
	"time"

	"github.com/giakiet05/uit-ai-assistant/backend/internal/model"
	"github.com/giakiet05/uit-ai-assistant/backend/internal/repo"
)

// --- Request DTOs ---

// ChatRequest for sending a chat message (with optional session ID)
type ChatRequest struct {
	Message   string  `json:"message" binding:"required,min=1,max=5000"`
	SessionID *string `json:"session_id" binding:"omitempty"` // If nil, creates new session
}

// CreateChatSessionRequest for creating a new chat session
type CreateChatSessionRequest struct {
	Title *string `json:"title" binding:"omitempty,max=100"` // Optional, auto-gen from first message if nil
}

// SendMessageRequest for sending a message in a chat session
type SendMessageRequest struct {
	Message string `json:"message" binding:"required,min=1,max=5000"`
}

// UpdateSessionTitleRequest for updating session title
type UpdateSessionTitleRequest struct {
	Title string `json:"title" binding:"required,min=1,max=100"`
}

// GetSessionsQuery for querying chat sessions with pagination
type GetSessionsQuery struct {
	Page     int `form:"page" binding:"omitempty,min=1"`
	PageSize int `form:"page_size" binding:"omitempty,min=1,max=100"`
}

// ToFindOptions converts query to repo.FindOptions
func (q *GetSessionsQuery) ToFindOptions() *repo.FindOptions {
	page := q.Page
	if page < 1 {
		page = 1
	}

	pageSize := q.PageSize
	if pageSize < 1 {
		pageSize = 20
	}
	if pageSize > 100 {
		pageSize = 100
	}

	return &repo.FindOptions{
		Skip:  int64((page - 1) * pageSize),
		Limit: int64(pageSize),
		Sort:  map[string]int{"updated_at": -1}, // Most recent first
	}
}

// GetMessagesQuery for querying messages with pagination
type GetMessagesQuery struct {
	Limit int `form:"limit" binding:"omitempty,min=1,max=100"` // Last N messages
}

// --- Response DTOs ---

// ChatResponse is returned after a successful chat
type ChatResponse struct {
	SessionID string              `json:"session_id"`
	Message   ChatMessageResponse `json:"message"` // The assistant's response
}

// ChatSessionResponse represents a chat session
type ChatSessionResponse struct {
	ID        string    `json:"id"`
	Title     string    `json:"title"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// SessionResponse is an alias for ChatSessionResponse (for backward compatibility)
type SessionResponse = ChatSessionResponse

// ChatMessageResponse represents a single chat message
type ChatMessageResponse struct {
	ID        string         `json:"id"`
	Role      string         `json:"role"` // "user" | "assistant"
	Content   string         `json:"content"`
	Metadata  map[string]any `json:"metadata,omitempty"` // Tool calls, sources, reasoning steps, etc.
	CreatedAt time.Time      `json:"created_at"`
}

// SourceInfo represents a reasoning-based RAG source citation
type SourceInfo struct {
	DocID     string     `json:"doc_id"`               // Document ID
	DocTitle  string     `json:"doc_title"`            // Document title
	DocType   string     `json:"doc_type"`             // "regulation" | "curriculum"
	Year      int        `json:"year"`                 // Document year
	SourceURL *string    `json:"source_url,omitempty"` // URL for curriculum (null for regulation)
	PDFURL    *string    `json:"pdf_url,omitempty"`    // PDF download URL for regulation (null for curriculum)
	Nodes     []NodeInfo `json:"nodes"`                // Referenced nodes
}

// NodeInfo represents a referenced node in a document
type NodeInfo struct {
	NodeID string `json:"node_id"` // Node ID (e.g., "0001")
	Title  string `json:"title"`   // Node title
	Text   string `json:"text"`    // Node text content (may be truncated)
}

// PaginatedSessionsResponse for paginated session list
type PaginatedSessionsResponse struct {
	Sessions   []ChatSessionResponse `json:"sessions"`
	Pagination Pagination            `json:"pagination"`
}

// PaginatedMessagesResponse for paginated message list
type PaginatedMessagesResponse struct {
	Messages []ChatMessageResponse `json:"messages"`
}

// --- Converter Functions ---

// FromChatSession converts model.ChatSession to ChatSessionResponse
func FromChatSession(s *model.ChatSession) *ChatSessionResponse {
	if s == nil {
		return nil
	}

	return &ChatSessionResponse{
		ID:        s.ID.Hex(),
		Title:     s.Title,
		CreatedAt: s.CreatedAt,
		UpdatedAt: s.UpdatedAt,
	}
}

// FromChatSessions converts multiple sessions to response DTOs
func FromChatSessions(sessions []*model.ChatSession) []ChatSessionResponse {
	responses := make([]ChatSessionResponse, len(sessions))
	for i, s := range sessions {
		resp := FromChatSession(s)
		if resp != nil {
			responses[i] = *resp
		}
	}
	return responses
}

// FromChatMessage converts model.ChatMessage to ChatMessageResponse
func FromChatMessage(m *model.ChatMessage) *ChatMessageResponse {
	if m == nil {
		return nil
	}

	return &ChatMessageResponse{
		ID:        m.ID.Hex(),
		Role:      string(m.Role),
		Content:   m.Content,
		Metadata:  m.Metadata,
		CreatedAt: m.CreatedAt,
	}
}

// FromChatMessages converts multiple messages to response DTOs
func FromChatMessages(messages []*model.ChatMessage) []ChatMessageResponse {
	responses := make([]ChatMessageResponse, len(messages))
	for i, m := range messages {
		resp := FromChatMessage(m)
		if resp != nil {
			responses[i] = *resp
		}
	}
	return responses
}

// GenerateSessionTitle generates a title from the first message
func GenerateSessionTitle(firstMessage string) string {
	maxLen := 50

	// Remove leading/trailing whitespace
	title := firstMessage

	// Truncate to maxLen
	if len(title) > maxLen {
		// Try to truncate at word boundary
		title = title[:maxLen]
		if lastSpace := len(title) - 1; lastSpace > 0 {
			for i := len(title) - 1; i >= 0; i-- {
				if title[i] == ' ' {
					title = title[:i]
					break
				}
			}
		}
		title = title + "..."
	}

	return title
}
