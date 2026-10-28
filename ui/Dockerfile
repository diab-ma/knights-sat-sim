FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci && sha256sum package-lock.json > node_modules/.knightsat-lock

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
