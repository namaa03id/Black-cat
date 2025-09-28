#!/usr/bin/env python3
"""
Omni-Engine Web Interface
Flask web application for the advanced web scraper
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import asyncio
import json
import os
from datetime import datetime
import logging
from omni_scraper import OmniScraper, ScrapedResult
import threading
import time
from werkzeug.serving import make_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config['SECRET_KEY'] = 'omni-engine-secret-key-2024'

# Global scraper instance
scraper = OmniScraper()

# In-memory storage for recent searches
recent_searches = []
MAX_RECENT_SEARCHES = 50

def add_to_recent_searches(query, results_count):
    """Add search to recent searches list"""
    global recent_searches
    
    search_entry = {
        'query': query,
        'results_count': results_count,
        'timestamp': datetime.now().isoformat()
    }
    
    recent_searches.insert(0, search_entry)
    recent_searches = recent_searches[:MAX_RECENT_SEARCHES]

@app.route('/')
def index():
    """Main search page"""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    """Handle search requests"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        max_results = int(data.get('max_results', 20))
        use_cache = data.get('use_cache', True)
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Query cannot be empty'
            }), 400
        
        logger.info(f"Search request: '{query}' (max_results: {max_results})")
        
        # Run async search in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(
                scraper.search(query, max_results=max_results, use_cache=use_cache)
            )
        finally:
            loop.close()
        
        # Convert results to JSON-serializable format
        results_data = []
        for result in results:
            results_data.append({
                'title': result.title,
                'url': result.url,
                'snippet': result.snippet,
                'content': result.content[:1000] if result.content else '',  # Truncate for web
                'source': result.source,
                'relevance_score': round(result.relevance_score, 3),
                'timestamp': result.timestamp.isoformat()
            })
        
        # Add to recent searches
        add_to_recent_searches(query, len(results))
        
        response_data = {
            'success': True,
            'query': query,
            'results_count': len(results),
            'results': results_data,
            'search_time': datetime.now().isoformat()
        }
        
        logger.info(f"Search completed: {len(results)} results for '{query}'")
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/export', methods=['POST'])
def export_results():
    """Export search results"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        format_type = data.get('format', 'json')
        results_data = data.get('results', [])
        
        # Convert back to ScrapedResult objects
        results = []
        for item in results_data:
            result = ScrapedResult(
                title=item['title'],
                url=item['url'],
                snippet=item['snippet'],
                content=item['content'],
                timestamp=datetime.fromisoformat(item['timestamp']),
                source=item['source'],
                relevance_score=item['relevance_score']
            )
            results.append(result)
        
        # Export data
        exported_data = scraper.export_results(results, format_type)
        
        if not exported_data:
            return jsonify({
                'success': False,
                'error': 'Failed to export data'
            }), 500
        
        # Save to file
        filename = f"omni_search_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        filepath = os.path.join('exports', filename)
        
        os.makedirs('exports', exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(exported_data)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'filepath': filepath
        })
    
    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Download exported file"""
    try:
        filepath = os.path.join('exports', filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/recent')
def get_recent_searches():
    """Get recent searches"""
    return jsonify({
        'success': True,
        'recent_searches': recent_searches
    })

@app.route('/stats')
def get_stats():
    """Get application statistics"""
    try:
        # Get database stats
        cursor = scraper.db_conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM scraped_data')
        total_cached = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT COUNT(DISTINCT query_hash) FROM scraped_data WHERE datetime(timestamp) > datetime('now', '-24 hours')"
        )
        queries_today = cursor.fetchone()[0]
        
        stats = {
            'success': True,
            'total_cached_results': total_cached,
            'unique_queries_today': queries_today,
            'recent_searches_count': len(recent_searches),
            'blocked_domains_count': len(scraper.blocked_domains),
            'supported_engines': list(scraper.search_engines.keys())
        }
        
        return jsonify(stats)
    
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    """Clear the search cache"""
    try:
        cursor = scraper.db_conn.cursor()
        cursor.execute('DELETE FROM scraped_data')
        scraper.db_conn.commit()
        
        global recent_searches
        recent_searches = []
        
        logger.info("Cache cleared successfully")
        return jsonify({
            'success': True,
            'message': 'Cache cleared successfully'
        })
    
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

class ServerThread(threading.Thread):
    """Thread to run Flask server"""
    
    def __init__(self, app, host='127.0.0.1', port=5000):
        threading.Thread.__init__(self)
        self.server = make_server(host, port, app)
        self.ctx = app.app_context()
        self.ctx.push()
        self.daemon = True
    
    def run(self):
        logger.info('Starting Omni-Engine server...')
        self.server.serve_forever()
    
    def shutdown(self):
        self.server.shutdown()

def start_server(host='127.0.0.1', port=5000, debug=False):
    """Start the Flask server"""
    if debug:
        app.run(host=host, port=port, debug=True)
    else:
        server_thread = ServerThread(app, host, port)
        server_thread.start()
        return server_thread

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Omni-Engine Web Scraper')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    
    args = parser.parse_args()
    
    print(f"""        
╔═══════════════════════════════════════════╗
║            OMNI-ENGINE SCRAPER            ║
║        Advanced Web Search Engine         ║
╠═══════════════════════════════════════════╣
║  Server: http://{args.host}:{args.port:<17} ║
║  Status: Starting...                      ║
╚═══════════════════════════════════════════╝
    """)
    
    try:
        start_server(host=args.host, port=args.port, debug=args.debug)
        
        if not args.debug:
            print(f"✅ Omni-Engine is running at http://{args.host}:{args.port}")
            print("Press Ctrl+C to stop the server")
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Shutting down Omni-Engine...")
    
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        print(f"❌ Error: {e}")