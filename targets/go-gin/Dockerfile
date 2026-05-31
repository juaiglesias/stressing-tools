FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod main.go ./
RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -o server .

FROM alpine:latest
RUN apk add --no-cache curl
WORKDIR /app
COPY --from=builder /app/server .
EXPOSE 3000
CMD ["./server"]
