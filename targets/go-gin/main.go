package main

import (
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

const mod = 1000000007

// O(n²) sobre n objetos + O(C³) multiplicación de matrices C×C (C=64).
func cpuCompute(n int) int {
	derived := make([]int, n)
	for i := 0; i < n; i++ {
		x := (i * 31) % 1000
		derived[i] = (x*2 + 1) % 1000
	}

	checksum := 0
	for i := 0; i < n; i++ {
		di := derived[i]
		for j := 0; j < n; j++ {
			checksum = (checksum + di*derived[j]) % mod
		}
	}

	C := 64
	for i := 0; i < C; i++ {
		for j := 0; j < C; j++ {
			s := 0
			for k := 0; k < C; k++ {
				s += ((i*C + k) % 100) * ((k + j) % 100)
			}
			checksum = (checksum + s) % mod
		}
	}
	return checksum
}

// Aloca n objetos anidados (todos vivos a la vez) y serializa una muestra.
func memAlloc(n int) gin.H {
	arr := make([]gin.H, n)
	for i := 0; i < n; i++ {
		arr[i] = gin.H{
			"id":      i,
			"name":    "item-" + strconv.Itoa(i),
			"tags":    []int{i, i + 1, i + 2},
			"payload": gin.H{"a": i % 100, "b": (i * 2) % 100, "c": (i * 3) % 100},
		}
	}
	sum := 0
	for i := 0; i < n; i++ {
		sum += i % 100
	}
	sample := arr
	if n > 100 {
		sample = arr[:100]
	}
	return gin.H{"count": n, "sum": sum, "sample": sample}
}

type payloadItem struct {
	ID     int    `json:"id"`
	Name   string `json:"name"`
	Value  int    `json:"value"`
	Active bool   `json:"active"`
}

type payloadBody struct {
	Items []payloadItem          `json:"items"`
	Meta  map[string]interface{} `json:"meta"`
}

func main() {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()

	r.GET("/holamundo", func(c *gin.Context) {
		c.JSON(200, gin.H{"mensaje": "hola mundo"})
	})

	r.GET("/dbquery", func(c *gin.Context) {
		time.Sleep(25 * time.Millisecond)
		rows := make([]gin.H, 10)
		for k := 0; k < 10; k++ {
			rows[k] = gin.H{"id": k, "value": k * 10}
		}
		c.JSON(200, gin.H{"rows": rows})
	})

	r.GET("/cpucompute", func(c *gin.Context) {
		n, err := strconv.Atoi(c.Query("n"))
		if err != nil || n <= 0 {
			n = 200
		}
		c.JSON(200, gin.H{"checksum": cpuCompute(n), "n": n})
	})

	r.GET("/memalloc", func(c *gin.Context) {
		n, err := strconv.Atoi(c.Query("n"))
		if err != nil || n <= 0 {
			n = 20000
		}
		c.JSON(200, memAlloc(n))
	})

	r.POST("/payload", func(c *gin.Context) {
		var body payloadBody
		if err := c.BindJSON(&body); err != nil {
			c.JSON(400, gin.H{"error": "invalid body"})
			return
		}
		activeCount := 0
		total := 0
		for _, it := range body.Items {
			if it.Active {
				activeCount++
				total += it.Value
			}
		}
		limit := len(body.Items)
		if limit > 10 {
			limit = 10
		}
		sample := make([]gin.H, 0, limit)
		for _, it := range body.Items[:limit] {
			sample = append(sample, gin.H{"id": it.ID, "name": strings.ToUpper(it.Name), "value": it.Value})
		}
		c.JSON(200, gin.H{
			"received":    len(body.Items),
			"activeCount": activeCount,
			"total":       total,
			"sample":      sample,
		})
	})

	r.Run(":3000")
}
