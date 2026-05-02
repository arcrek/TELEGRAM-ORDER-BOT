# syntax=docker/dockerfile:1
#
# Multistage build for the React frontend (Vite) served via nginx.

########################
# Builder
########################
FROM node:18-alpine AS builder

WORKDIR /app

# Install deps — prefer ci (lockfile-exact) over install
COPY package*.json ./
RUN npm ci

COPY . .

# Accept build argument for API URL
ARG VITE_API_BASE_URL=http://localhost:8001
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

########################
# Runtime
########################
FROM nginx:alpine

# Remove default config and add SPA-friendly config
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

