FROM node:20-alpine AS build

WORKDIR /app

# VITE_API_BASE_URL must be set at build time — Vite inlines it into the
# bundle and it cannot be changed at runtime without a rebuild.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Copy pre-installed node_modules from the host to avoid running npm install
# inside Docker (requires network access).
COPY package*.json ./
COPY node_modules ./node_modules

COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS serve

RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/app.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
