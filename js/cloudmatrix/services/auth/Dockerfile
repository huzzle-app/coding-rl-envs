FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/auth/ ./services/auth/
RUN npm install --workspace=services/auth
CMD ["node", "services/auth/src/index.js"]
