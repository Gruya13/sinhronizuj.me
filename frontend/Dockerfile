# Faza 1: Build aplikacije
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Faza 2: Runtime Nginx
FROM nginx:alpine

# Kopiranje izgrađenih fajlova
COPY --from=builder /app/dist /usr/share/nginx/html

# Kopiranje Nginx konfiguracije
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
