package main

import "github.com/gin-gonic/gin"

func main() {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.GET("/holamundo", func(c *gin.Context) {
		c.JSON(200, gin.H{"mensaje": "hola mundo"})
	})
	r.Run(":3000")
}
