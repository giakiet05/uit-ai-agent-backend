package service

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	platformgrpc "github.com/giakiet05/uit-ai-assistant/backend/internal/platform/grpc"
)

// SourceEnricher enriches reasoning sources with full metadata
type SourceEnricher interface {
	EnrichSources(sources []platformgrpc.ReasoningSource) ([]EnrichedSource, error)
}

type sourceEnricher struct {
	dataDir string // Path to data/ directory
	baseURL string // Base URL for building PDF links
}

// NewSourceEnricher creates a new source enricher
func NewSourceEnricher(dataDir, baseURL string) SourceEnricher {
	return &sourceEnricher{
		dataDir: dataDir,
		baseURL: baseURL,
	}
}

// EnrichedSource represents a fully enriched source with metadata
type EnrichedSource struct {
	DocID      string     `json:"doc_id"`       // Document ID
	DocTitle   string     `json:"doc_title"`    // Document title from ToC
	DocType    string     `json:"doc_type"`     // "regulation" | "curriculum"
	Year       int        `json:"year"`         // Document year
	SourceURL  *string    `json:"source_url"`   // URL for curriculum (null for regulation)
	PDFURL     *string    `json:"pdf_url"`      // PDF download URL for regulation (null for curriculum)
	Nodes      []NodeInfo `json:"nodes"`        // Enriched nodes
}

// NodeInfo represents enriched node information
type NodeInfo struct {
	NodeID string `json:"node_id"` // Node ID (e.g., "0001")
	Title  string `json:"title"`   // Node title
	Text   string `json:"text"`    // Node text content
}

// TocIndex represents the structure of toc_index.json
type TocIndex struct {
	TotalDocuments int           `json:"total_documents"`
	Documents      []TocDocument `json:"documents"`
}

// TocDocument represents a document entry in toc_index.json
type TocDocument struct {
	DocID     string  `json:"doc_id"`
	DocName   string  `json:"doc_name"`
	TocPath   string  `json:"toc_path"`
	Summary   string  `json:"summary"`
	Year      int     `json:"year"`
	DocType   string  `json:"doc_type"`
	SourceURL *string `json:"source_url"`
}

// TocStructure represents the structure of individual ToC files
type TocStructure struct {
	DocName   string `json:"doc_name"`
	Structure []Node `json:"structure"`
}

// Node represents a node in the ToC tree
type Node struct {
	Title   string  `json:"title"`
	NodeID  string  `json:"node_id"`
	Text    string  `json:"text"`
	Nodes   []Node  `json:"nodes,omitempty"`
}

// EnrichSources enriches reasoning sources with full metadata from ToC files
func (e *sourceEnricher) EnrichSources(sources []platformgrpc.ReasoningSource) ([]EnrichedSource, error) {
	if len(sources) == 0 {
		return []EnrichedSource{}, nil
	}

	// Load ToC index
	tocIndex, err := e.loadTocIndex()
	if err != nil {
		return nil, fmt.Errorf("failed to load ToC index: %w", err)
	}

	// Build doc_id -> TocDocument map
	docMap := make(map[string]TocDocument)
	for _, doc := range tocIndex.Documents {
		docMap[doc.DocID] = doc
	}

	// Enrich each source
	enrichedSources := make([]EnrichedSource, 0, len(sources))

	for _, src := range sources {
		// Get doc metadata from index
		docMeta, exists := docMap[src.DocID]
		if !exists {
			// Document not found in index - skip
			continue
		}

		// Load ToC structure to get node details
		tocStructure, err := e.loadTocStructure(docMeta.TocPath)
		if err != nil {
			// Skip if ToC structure not found
			continue
		}

		// Build node_id -> Node map
		nodeMap := e.buildNodeMap(tocStructure.Structure)

		// Enrich nodes
		nodes := make([]NodeInfo, 0, len(src.NodeIDs))
		for _, nodeID := range src.NodeIDs {
			if node, exists := nodeMap[nodeID]; exists {
				nodes = append(nodes, NodeInfo{
					NodeID: nodeID,
					Title:  node.Title,
					Text:   node.Text,
				})
			}
		}

		// Build PDF URL (only for regulation)
		var pdfURL *string
		if docMeta.DocType == "regulation" {
			url := fmt.Sprintf("%s/api/v1/files/regulation/%s.pdf", e.baseURL, src.DocID)
			pdfURL = &url
		}

		enrichedSources = append(enrichedSources, EnrichedSource{
			DocID:     src.DocID,
			DocTitle:  docMeta.DocName,
			DocType:   docMeta.DocType,
			Year:      docMeta.Year,
			SourceURL: docMeta.SourceURL,
			PDFURL:    pdfURL,
			Nodes:     nodes,
		})
	}

	return enrichedSources, nil
}

// loadTocIndex loads toc_index.json
func (e *sourceEnricher) loadTocIndex() (*TocIndex, error) {
	indexPath := filepath.Join(e.dataDir, "toc", "toc_index.json")
	
	data, err := os.ReadFile(indexPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read toc_index.json: %w", err)
	}

	var index TocIndex
	if err := json.Unmarshal(data, &index); err != nil {
		return nil, fmt.Errorf("failed to parse toc_index.json: %w", err)
	}

	return &index, nil
}

// loadTocStructure loads individual ToC structure file
func (e *sourceEnricher) loadTocStructure(tocPath string) (*TocStructure, error) {
	structurePath := filepath.Join(e.dataDir, "toc", tocPath)
	
	data, err := os.ReadFile(structurePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read ToC structure: %w", err)
	}

	var structure TocStructure
	if err := json.Unmarshal(data, &structure); err != nil {
		return nil, fmt.Errorf("failed to parse ToC structure: %w", err)
	}

	return &structure, nil
}

// buildNodeMap recursively builds a map of node_id -> Node
func (e *sourceEnricher) buildNodeMap(nodes []Node) map[string]Node {
	nodeMap := make(map[string]Node)
	
	var traverse func([]Node)
	traverse = func(nodes []Node) {
		for _, node := range nodes {
			nodeMap[node.NodeID] = node
			if len(node.Nodes) > 0 {
				traverse(node.Nodes)
			}
		}
	}
	
	traverse(nodes)
	return nodeMap
}
