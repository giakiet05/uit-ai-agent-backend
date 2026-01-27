package controller

import (
	"fmt"
	"net/http"
	"path/filepath"
	"strings"

	"github.com/giakiet05/uit-ai-assistant/backend/internal/apperror"
	"github.com/gin-gonic/gin"
)

type FileController struct {
	dataDir string
}

func NewFileController(dataDir string) *FileController {
	return &FileController{
		dataDir: dataDir,
	}
}

// ServeRegulationPDF serves PDF files from data/raw/regulation/
func (fc *FileController) ServeRegulationPDF(c *gin.Context) {
	filename := c.Param("filename")

	// Validate filename (prevent path traversal)
	if strings.Contains(filename, "..") || strings.Contains(filename, "/") {
		c.JSON(http.StatusBadRequest, gin.H{"error": apperror.ErrBadRequest.Message})
		return
	}

	// Ensure .pdf extension
	if !strings.HasSuffix(filename, ".pdf") {
		c.JSON(http.StatusBadRequest, gin.H{"error": apperror.ErrBadRequest.Message})
		return
	}

	// Construct file path
	filePath := filepath.Join(fc.dataDir, "raw", "regulation", filename)

	// Check if file exists and serve
	c.Header("Content-Type", "application/pdf")
	c.Header("Content-Disposition", fmt.Sprintf("inline; filename=%s", filename))
	c.File(filePath)
}
