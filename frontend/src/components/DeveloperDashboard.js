import React, { useState } from "react";
import axios from "axios";
import "./DeveloperDashboard.css";

const DeveloperDashboard = () => {
  const [endpoint, setEndpoint] = useState("");
  const [response, setResponse] = useState(null);
  const [requestBody, setRequestBody] = useState("{}");
  const [loading, setLoading] = useState(false);

  const handleTestEndpoint = async () => {
    setLoading(true);
    try {
      const res = await axios.post(endpoint, JSON.parse(requestBody));
      setResponse(res.data);
    } catch (error) {
      setResponse(error.response ? error.response.data : error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="developer-dashboard">
      <h1>Developer Dashboard</h1>
      <div className="form-group">
        <label>Endpoint URL:</label>
        <input
          type="text"
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
          placeholder="http://localhost:8000/api/test"
          className="form-control"
        />
      </div>
      <div className="form-group">
        <label>Request Body (JSON):</label>
        <textarea
          value={requestBody}
          onChange={(e) => setRequestBody(e.target.value)}
          placeholder='{"key": "value"}'
          className="form-control textarea-control"
        />
      </div>
      <button
        onClick={handleTestEndpoint}
        className="btn btn-primary"
        disabled={loading}
      >
        {loading ? "Testing..." : "Test Endpoint"}
      </button>
      <div className="response-section">
        <h2>Response:</h2>
        <pre className="response-pre">
          {response ? JSON.stringify(response, null, 2) : "No response yet."}
        </pre>
      </div>
    </div>
  );
};

export default DeveloperDashboard;
