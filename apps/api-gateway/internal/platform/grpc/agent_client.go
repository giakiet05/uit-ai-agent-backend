package grpc

import (
	"context"
	"fmt"
	"time"

	"github.com/giakiet05/uit-ai-assistant/backend/internal/platform/grpc/pb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// AgentClient wraps the gRPC client for the Agent service
type AgentClient struct {
	conn   *grpc.ClientConn
	client pb.AgentClient
}

// NewAgentClient creates a new AgentClient connected to the specified address
func NewAgentClient(addr string) (*AgentClient, error) {
	// Dial options
	opts := []grpc.DialOption{
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithDefaultCallOptions(
			grpc.MaxCallRecvMsgSize(50*1024*1024), // 50MB
			grpc.MaxCallSendMsgSize(50*1024*1024), // 50MB
		),
	}

	// Dial gRPC server
	conn, err := grpc.NewClient(addr, opts...)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to agent gRPC server at %s: %w", addr, err)
	}

	// Create client
	client := pb.NewAgentClient(conn)

	return &AgentClient{
		conn:   conn,
		client: client,
	}, nil
}

// Close closes the gRPC connection
func (c *AgentClient) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

// Chat sends a chat request to the agent and returns the response
// Uses stateful architecture with thread_id for conversation persistence
func (c *AgentClient) Chat(ctx context.Context, message string, userID string, threadID string) (*AgentResponse, error) {
	// Create request (no history needed - LangGraph checkpointer manages state)
	req := &pb.ChatRequest{
		Message:  message,
		UserId:   userID,
		ThreadId: threadID,
	}

	// Set timeout (10 minutes for complex retrievals with MCP tools)
	callCtx, cancel := context.WithTimeout(ctx, 10*time.Minute)
	defer cancel()

	// Call gRPC
	resp, err := c.client.Chat(callCtx, req)
	if err != nil {
		return nil, fmt.Errorf("gRPC call failed: %w", err)
	}

	// Convert response
	return c.convertResponse(resp), nil
}

// convertResponse converts protobuf ChatResponse to AgentResponse
func (c *AgentClient) convertResponse(resp *pb.ChatResponse) *AgentResponse {
	// Convert sources (ReasoningSource with just IDs)
	sources := make([]ReasoningSource, len(resp.Sources))
	for i, src := range resp.Sources {
		sources[i] = ReasoningSource{
			DocID:   src.DocId,
			NodeIDs: src.NodeIds,
		}
	}

	return &AgentResponse{
		Content:    resp.Content,
		Sources:    sources,
		TokensUsed: int(resp.TokensUsed),
		LatencyMs:  int(resp.LatencyMs),
	}
}

// AgentResponse represents the response from the agent
type AgentResponse struct {
	Content    string            // Clean response text
	Sources    []ReasoningSource // Reasoning-based RAG sources (doc_id + node_ids)
	TokensUsed int               // Tokens used (currently 0)
	LatencyMs  int               // Latency in milliseconds (currently 0)
}

// ReasoningSource represents a reasoning-based RAG source (IDs only)
type ReasoningSource struct {
	DocID   string   // Document ID (e.g., "159-qd-dhcntt_05-03-2024...")
	NodeIDs []string // Node IDs used from this document (e.g., ["0001", "0002"])
}
