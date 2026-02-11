FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/users/ ./services/users/
RUN npm install --workspace=services/users
CMD ["node", "services/users/src/index.js"]
