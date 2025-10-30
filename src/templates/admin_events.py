"""
Admin Events Viewer
HTML template for viewing analytics events
"""

ADMIN_EVENTS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analytics Events - Admin Panel</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            color: #e2e8f0;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            background: rgba(15, 23, 42, 0.8);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(148, 163, 184, 0.3);
        }
        
        .header h1 {
            margin: 0;
            color: #22c55e;
            font-size: 2rem;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .stat-card {
            background: rgba(30, 41, 59, 0.8);
            padding: 15px;
            border-radius: 8px;
            border: 1px solid rgba(148, 163, 184, 0.3);
            text-align: center;
        }
        
        .stat-value {
            font-size: 2rem;
            font-weight: bold;
            color: #22c55e;
            display: block;
        }
        
        .stat-label {
            font-size: 0.9rem;
            color: #94a3b8;
            margin-top: 5px;
        }
        
        .filters {
            background: rgba(30, 41, 59, 0.8);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            border: 1px solid rgba(148, 163, 184, 0.3);
        }
        
        .filter-row {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }
        
        .filter-group {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        .filter-group label {
            font-size: 0.9rem;
            color: #94a3b8;
        }
        
        .filter-group select,
        .filter-group input {
            padding: 8px 12px;
            border: 1px solid rgba(148, 163, 184, 0.3);
            border-radius: 6px;
            background: rgba(15, 23, 42, 0.8);
            color: #e2e8f0;
            font-size: 0.9rem;
        }
        
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.3s ease;
        }
        
        .btn-primary {
            background: #22c55e;
            color: white;
        }
        
        .btn-primary:hover {
            background: #16a34a;
        }
        
        .btn-secondary {
            background: rgba(148, 163, 184, 0.3);
            color: #e2e8f0;
        }
        
        .btn-secondary:hover {
            background: rgba(148, 163, 184, 0.5);
        }
        
        .events-container {
            background: rgba(30, 41, 59, 0.8);
            border-radius: 8px;
            border: 1px solid rgba(148, 163, 184, 0.3);
            overflow: hidden;
        }
        
        .events-header {
            background: rgba(15, 23, 42, 0.9);
            padding: 15px 20px;
            border-bottom: 1px solid rgba(148, 163, 184, 0.3);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .events-count {
            color: #94a3b8;
            font-size: 0.9rem;
        }
        
        .events-list {
            max-height: 600px;
            overflow-y: auto;
        }
        
        .event-item {
            padding: 15px 20px;
            border-bottom: 1px solid rgba(148, 163, 184, 0.1);
            transition: background 0.2s ease;
        }
        
        .event-item:hover {
            background: rgba(51, 65, 85, 0.3);
        }
        
        .event-item:last-child {
            border-bottom: none;
        }
        
        .event-header {
            display: flex;
            justify-content: between;
            align-items: center;
            margin-bottom: 8px;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .event-type {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .event-type.session_started { background: #22c55e; color: white; }
        .event-type.session_ended { background: #ef4444; color: white; }
        .event-type.message_exchanged { background: #3b82f6; color: white; }
        .event-type.test_ping { background: #8b5cf6; color: white; }
        
        .event-time {
            color: #94a3b8;
            font-size: 0.85rem;
            margin-left: auto;
        }
        
        .event-user {
            color: #22c55e;
            font-size: 0.85rem;
            font-weight: 500;
        }
        
        .event-payload {
            background: rgba(15, 23, 42, 0.6);
            padding: 10px;
            border-radius: 6px;
            margin-top: 8px;
            font-family: 'Courier New', monospace;
            font-size: 0.8rem;
            color: #cbd5e1;
            white-space: pre-wrap;
            overflow-x: auto;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #94a3b8;
        }
        
        .error {
            background: rgba(220, 38, 38, 0.2);
            border: 1px solid #dc2626;
            color: #fca5a5;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        
        .pagination {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-top: 20px;
        }
        
        @media (max-width: 768px) {
            .filter-row {
                flex-direction: column;
                align-items: stretch;
            }
            
            .event-header {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .event-time {
                margin-left: 0;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Analytics Events Viewer</h1>
            <p>Real-time monitoring of user analytics and system events</p>
        </div>
        
        <div id="stats" class="stats-grid">
            <!-- Stats will be loaded here -->
        </div>
        
        <div class="filters">
            <div class="filter-row">
                <div class="filter-group">
                    <label>User ID</label>
                    <input type="text" id="userFilter" placeholder="Filter by user ID">
                </div>
                <div class="filter-group">
                    <label>Event Type</label>
                    <select id="eventTypeFilter">
                        <option value="">All Types</option>
                        <option value="session_started">Session Started</option>
                        <option value="session_ended">Session Ended</option>
                        <option value="message_exchanged">Message Exchanged</option>
                        <option value="test_ping">Test Ping</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Days Back</label>
                    <select id="daysFilter">
                        <option value="1">Last 24 hours</option>
                        <option value="7" selected>Last 7 days</option>
                        <option value="30">Last 30 days</option>
                        <option value="0">All time</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>&nbsp;</label>
                    <button class="btn btn-primary" onclick="loadEvents()">🔄 Refresh</button>
                </div>
                <div class="filter-group">
                    <label>&nbsp;</label>
                    <button class="btn btn-secondary" onclick="exportEvents()">📥 Export</button>
                </div>
            </div>
        </div>
        
        <div class="events-container">
            <div class="events-header">
                <h3>Recent Events</h3>
                <span id="eventsCount" class="events-count">Loading...</span>
            </div>
            <div id="eventsList" class="events-list">
                <div class="loading">Loading events...</div>
            </div>
        </div>
        
        <div id="pagination" class="pagination" style="display: none;">
            <!-- Pagination will be added here -->
        </div>
    </div>

    <script>
        let allEvents = [];
        let filteredEvents = [];
        let currentPage = 1;
        const eventsPerPage = 50;
        
        // Load events on page load
        document.addEventListener('DOMContentLoaded', function() {
            loadEvents();
            
            // Auto-refresh every 30 seconds
            setInterval(loadEvents, 30000);
        });
        
        async function loadEvents() {
            try {
                const response = await fetch('/api/v2/admin/events');
                const data = await response.json();
                
                if (data.success) {
                    allEvents = data.events || [];
                    loadStats(data.stats || {});
                    applyFilters();
                } else {
                    showError('Failed to load events: ' + (data.error || 'Unknown error'));
                }
            } catch (error) {
                showError('Network error: ' + error.message);
            }
        }
        
        function loadStats(stats) {
            const statsHTML = `
                <div class="stat-card">
                    <span class="stat-value">${stats.total_events || 0}</span>
                    <div class="stat-label">Total Events</div>
                </div>
                <div class="stat-card">
                    <span class="stat-value">${stats.unique_users || 0}</span>
                    <div class="stat-label">Unique Users</div>
                </div>
                <div class="stat-card">
                    <span class="stat-value">${stats.sessions_started || 0}</span>
                    <div class="stat-label">Sessions Started</div>
                </div>
                <div class="stat-card">
                    <span class="stat-value">${stats.messages_exchanged || 0}</span>
                    <div class="stat-label">Messages Exchanged</div>
                </div>
            `;
            document.getElementById('stats').innerHTML = statsHTML;
        }
        
        function applyFilters() {
            const userFilter = document.getElementById('userFilter').value.toLowerCase();
            const eventTypeFilter = document.getElementById('eventTypeFilter').value;
            const daysFilter = parseInt(document.getElementById('daysFilter').value);
            
            filteredEvents = allEvents.filter(event => {
                // User filter
                if (userFilter && !event.user_id.toLowerCase().includes(userFilter)) {
                    return false;
                }
                
                // Event type filter
                if (eventTypeFilter && event.event_type !== eventTypeFilter) {
                    return false;
                }
                
                // Days filter
                if (daysFilter > 0) {
                    const eventDate = new Date(event.timestamp);
                    const cutoff = new Date();
                    cutoff.setDate(cutoff.getDate() - daysFilter);
                    if (eventDate < cutoff) {
                        return false;
                    }
                }
                
                return true;
            });
            
            currentPage = 1;
            renderEvents();
        }
        
        function renderEvents() {
            const startIdx = (currentPage - 1) * eventsPerPage;
            const endIdx = startIdx + eventsPerPage;
            const pageEvents = filteredEvents.slice(startIdx, endIdx);
            
            document.getElementById('eventsCount').textContent = 
                `Showing ${startIdx + 1}-${Math.min(endIdx, filteredEvents.length)} of ${filteredEvents.length} events`;
            
            if (pageEvents.length === 0) {
                document.getElementById('eventsList').innerHTML = 
                    '<div class="loading">No events found matching your filters.</div>';
                return;
            }
            
            const eventsHTML = pageEvents.map(event => `
                <div class="event-item">
                    <div class="event-header">
                        <span class="event-type ${event.event_type}">${event.event_type}</span>
                        <span class="event-user">👤 ${event.user_id}</span>
                        <span class="event-time">🕐 ${formatTimestamp(event.timestamp)}</span>
                    </div>
                    <div class="event-payload">${JSON.stringify(event.payload, null, 2)}</div>
                </div>
            `).join('');
            
            document.getElementById('eventsList').innerHTML = eventsHTML;
            
            // Update pagination
            renderPagination();
        }
        
        function renderPagination() {
            const totalPages = Math.ceil(filteredEvents.length / eventsPerPage);
            
            if (totalPages <= 1) {
                document.getElementById('pagination').style.display = 'none';
                return;
            }
            
            let paginationHTML = '';
            
            // Previous button
            if (currentPage > 1) {
                paginationHTML += `<button class="btn btn-secondary" onclick="changePage(${currentPage - 1})">← Previous</button>`;
            }
            
            // Page numbers
            for (let i = Math.max(1, currentPage - 2); i <= Math.min(totalPages, currentPage + 2); i++) {
                const isActive = i === currentPage ? 'btn-primary' : 'btn-secondary';
                paginationHTML += `<button class="btn ${isActive}" onclick="changePage(${i})">${i}</button>`;
            }
            
            // Next button
            if (currentPage < totalPages) {
                paginationHTML += `<button class="btn btn-secondary" onclick="changePage(${currentPage + 1})">Next →</button>`;
            }
            
            document.getElementById('pagination').innerHTML = paginationHTML;
            document.getElementById('pagination').style.display = 'flex';
        }
        
        function changePage(page) {
            currentPage = page;
            renderEvents();
        }
        
        function formatTimestamp(timestamp) {
            const date = new Date(timestamp);
            return date.toLocaleString();
        }
        
        function showError(message) {
            const errorHTML = `<div class="error">❌ Error: ${message}</div>`;
            document.getElementById('eventsList').innerHTML = errorHTML;
        }
        
        async function exportEvents() {
            try {
                const csvContent = generateCSV(filteredEvents);
                downloadCSV(csvContent, 'analytics_events.csv');
            } catch (error) {
                alert('Export failed: ' + error.message);
            }
        }
        
        function generateCSV(events) {
            const headers = ['Timestamp', 'User ID', 'Event Type', 'Payload'];
            const rows = events.map(event => [
                event.timestamp,
                event.user_id,
                event.event_type,
                JSON.stringify(event.payload).replace(/"/g, '""')  // Escape quotes for CSV
            ]);
            
            const csvContent = [headers, ...rows]
                .map(row => row.map(field => `"${field}"`).join(','))
                .join('\\n');
            
            return csvContent;
        }
        
        function downloadCSV(csvContent, filename) {
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);
            link.setAttribute('href', url);
            link.setAttribute('download', filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
        
        // Add event listeners for filters
        document.getElementById('userFilter').addEventListener('input', applyFilters);
        document.getElementById('eventTypeFilter').addEventListener('change', applyFilters);
        document.getElementById('daysFilter').addEventListener('change', applyFilters);
    </script>
</body>
</html>
"""