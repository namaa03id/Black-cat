#!/usr/bin/env python3
"""
Omni-Engine Quick Start Script
Simple script to launch the Omni-Engine web scraper
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def check_python_version():
    """Check if Python version is 3.8 or higher"""
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required")
        print(f"   Current version: {sys.version}")
        sys.exit(1)
    else:
        print(f"✅ Python {sys.version.split()[0]} detected")

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = [
        'flask', 'requests', 'beautifulsoup4', 
        'aiohttp', 'fake_useragent'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing packages: {', '.join(missing_packages)}")
        print("   Installing dependencies...")
        
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 
                '-r', 'requirements.txt'
            ])
            print("✅ Dependencies installed successfully")
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies")
            print("   Please run: pip install -r requirements.txt")
            sys.exit(1)
    else:
        print("✅ All dependencies are installed")

def setup_directories():
    """Create necessary directories"""
    directories = ['static', 'templates', 'exports']
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    
    print("✅ Directory structure verified")

def main():
    parser = argparse.ArgumentParser(description='Omni-Engine Web Scraper')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--skip-checks', action='store_true', help='Skip dependency checks')
    
    args = parser.parse_args()
    
    print("""
    ╔═══════════════════════════════════════════╗
    ║            OMNI-ENGINE LAUNCHER           ║
    ║        Advanced Web Scraping Tool         ║
    ╚═══════════════════════════════════════════╝
    """)
    
    if not args.skip_checks:
        print("🔍 Performing system checks...")
        check_python_version()
        check_dependencies()
        setup_directories()
        print()
    
    print(f"🚀 Starting Omni-Engine server...")
    print(f"   Host: {args.host}")
    print(f"   Port: {args.port}")
    print(f"   Debug: {args.debug}")
    print(f"   URL: http://{args.host}:{args.port}")
    print()
    
    try:
        # Import and run the Flask app
        from app import start_server
        
        if args.debug:
            print("🔧 Debug mode enabled - auto-reload on code changes")
            from app import app
            app.run(host=args.host, port=args.port, debug=True)
        else:
            start_server(host=args.host, port=args.port, debug=False)
            print(f"✅ Omni-Engine is running at http://{args.host}:{args.port}")
            print("📝 Check omni_scraper.log for detailed logs")
            print("⏹️  Press Ctrl+C to stop the server")
            
            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Shutting down Omni-Engine...")
                print("👋 Thank you for using Omni-Engine!")
    
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure all files are in place and dependencies are installed")
        sys.exit(1)
    
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()