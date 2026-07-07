# --- build ---------------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# Variáveis VITE_* são "assadas" no build (client-side). Passe via build args
# no docker-compose. Sem GOOGLE_CLIENT_ID, o login usa o modo dev.
ARG VITE_GOOGLE_CLIENT_ID=
ARG VITE_DEV_AUTH=true
ARG VITE_EXTRACAO_IA_ENABLED=true
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
ENV VITE_DEV_AUTH=$VITE_DEV_AUTH
ENV VITE_EXTRACAO_IA_ENABLED=$VITE_EXTRACAO_IA_ENABLED
RUN npm run build

# --- serve ---------------------------------------------------------------
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
