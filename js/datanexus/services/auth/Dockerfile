FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/auth/ ./services/auth/
RUN npm install --workspace=services/auth
EXPOSE 3001
CMD ["node", "services/auth/src/index.js"]
