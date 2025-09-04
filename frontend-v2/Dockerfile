FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
# Ensure development dependencies like Vite are installed
ENV NODE_ENV=development
RUN npm install

COPY . .

CMD ["npm", "run", "dev"]
