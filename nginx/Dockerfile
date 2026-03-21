FROM node:25-alpine AS frontend-builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci --silent --no-audit --no-fund

COPY frontend/ ./

ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

FROM nginx:1.27-alpine

COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
