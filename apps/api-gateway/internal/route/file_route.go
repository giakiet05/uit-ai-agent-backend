package route

import (
	"github.com/giakiet05/uit-ai-assistant/backend/internal/controller"
	"github.com/gin-gonic/gin"
)

func RegisterFileRoutes(rg *gin.RouterGroup, fc *controller.FileController) {
	files := rg.Group("/files")
	{
		// Serve regulation PDFs
		files.GET("/regulation/:filename", fc.ServeRegulationPDF)
	}
}
