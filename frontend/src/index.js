/** Application entry point - renders root React component to DOM */
import React from "react";
import ReactDOM from "react-dom/client";
import "./global-variables.css";
import App from "./App";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
