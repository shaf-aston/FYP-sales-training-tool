# Fitness Chatbot - React Frontend

A modern React.js frontend for the Fitness Chatbot application.

## Features

- Modern, responsive React UI
- Real-time chat with Mary (65-year-old fitness client simulation)
- Typing indicators and smooth animations
- Mobile-friendly design
- Integration with FastAPI backend

## Quick Start

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Start the development server:**
   ```bash
   npm start
   ```

3. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000 (must be running separately)

## Available Scripts

- `npm start` - Runs the app in development mode
- `npm build` - Builds the app for production
- `npm test` - Launches the test runner
- `npm eject` - Ejects from Create React App (one-way operation)

## Backend Integration

The React app communicates with the FastAPI backend through these endpoints:
- `GET /api/greeting` - Fetch Mary's initial greeting
- `POST /api/chat` - Send messages and receive responses

Make sure the FastAPI backend is running on http://localhost:8000 before starting the React development server.

## Deployment

For production deployment:
1. Build the React app: `npm run build`
2. Serve the built files using a static file server or integrate with the FastAPI backend
3. Configure CORS settings in the backend for your production domain

## Technologies Used

- React 18
- Axios for API calls
- CSS3 with modern animations
- Responsive design principles