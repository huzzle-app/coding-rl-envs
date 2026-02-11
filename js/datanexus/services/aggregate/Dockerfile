FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/aggregate/ ./services/aggregate/
RUN npm install --workspace=services/aggregate
EXPOSE 3005
CMD ["node", "services/aggregate/src/index.js"]
