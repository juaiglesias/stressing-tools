FROM rust:alpine AS builder
RUN apk add --no-cache musl-dev
WORKDIR /app
COPY Cargo.toml ./
# Cache dependencies: build a dummy binary first
RUN mkdir src && echo "fn main() {}" > src/main.rs && cargo build --release && rm -f target/release/deps/server*
COPY src ./src
RUN cargo build --release

FROM alpine:latest
RUN apk add --no-cache curl
WORKDIR /app
COPY --from=builder /app/target/release/server .
EXPOSE 3000
CMD ["./server"]
