# syntax=docker/dockerfile:1
FROM node:22.22.3-alpine AS build

WORKDIR /app

# Local file dependencies in the Console lockfile must exist before npm ci.
COPY packages/ ./packages/
COPY plugins/ ./plugins/
COPY extensions/ ./extensions/
COPY mixtum_instance/ ./mixtum_instance/

WORKDIR /app/console
COPY console/package*.json ./
RUN npm ci

COPY console/ ./
RUN npm run build -- --configuration production

FROM nginx:alpine
COPY --from=build /app/console/dist/adr-payment-hub/browser/ /usr/share/nginx/html/
