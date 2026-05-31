FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json nest-cli.json tsconfig.json ./
RUN npm install
COPY src/ ./src/
RUN npm run build

FROM node:20-alpine
RUN apk add --no-cache curl
WORKDIR /app
COPY package*.json ./
RUN npm install --omit=dev
COPY --from=builder /app/dist ./dist
EXPOSE 3000
CMD ["node", "dist/main"]
