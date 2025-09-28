#!/usr/bin/env python3
"""
Omni-Engine Web Scraper
A powerful web scraping engine with advanced features and error handling
"""

import requests
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
import time
import random
from urllib.parse import urljoin, urlparse, parse_qs
from dataclasses import dataclass
from typing import List, Dict, Optional, Union
import logging
import re
from fake_useragent import UserAgent
from urllib.robotparser import RobotFileParser
from datetime import datetime
import hashlib
import sqlite3
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('omni_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ScrapedResult:
    """Data structure for scraped results"""
    title: str
    url: str
    snippet: str
    content: str
    timestamp: datetime
    source: str
    relevance_score: float = 0.0
    metadata: Dict = None

class OmniScraper:
    """Advanced web scraper with multiple search engines and error handling"""
    
    def __init__(self, delay_range=(1, 3), max_retries=3):
        self.delay_range = delay_range
        self.max_retries = max_retries
        self.ua = UserAgent()
        self.session = None
        self.results_cache = {}
        self.blocked_domains = set()
        
        # Initialize database
        self.init_database()
        
        # Search engines configuration (free alternatives)
        self.search_engines = {
            'duckduckgo': {
                'url': 'https://duckduckgo.com/html/',
                'params': {'q': '{query}'},
                'parser': self._parse_duckduckgo
            },
            'bing': {
                'url': 'https://www.bing.com/search',
                'params': {'q': '{query}'},
                'parser': self._parse_bing
            },
            'yahoo': {
                'url': 'https://search.yahoo.com/search',
                'params': {'p': '{query}'},
                'parser': self._parse_yahoo
            }
        }
    
    def init_database(self):
        """Initialize SQLite database for caching results"""
        try:
            self.db_conn = sqlite3.connect('omni_cache.db', check_same_thread=False)
            cursor = self.db_conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scraped_data (
                    id INTEGER PRIMARY KEY,
                    query_hash TEXT,
                    title TEXT,
                    url TEXT,
                    snippet TEXT,
                    content TEXT,
                    source TEXT,
                    timestamp DATETIME,
                    relevance_score REAL
                )
            ''')
            self.db_conn.commit()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    def get_headers(self):
        """Generate random headers to avoid detection"""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def respect_robots_txt(self, url: str) -> bool:
        """Check if scraping is allowed by robots.txt"""
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            return rp.can_fetch(self.ua.random, url)
        except Exception as e:
            logger.warning(f"Could not check robots.txt for {url}: {e}")
            return True  # Allow if robots.txt is not accessible
    
    async def fetch_url(self, session, url: str, params: dict = None) -> Optional[str]:
        """Fetch URL content with error handling and retries"""
        
        if not self.respect_robots_txt(url):
            logger.warning(f"Robots.txt disallows scraping {url}")
            return None
        
        for attempt in range(self.max_retries):
            try:
                await asyncio.sleep(random.uniform(*self.delay_range))
                
                async with session.get(
                    url, 
                    params=params,
                    headers=self.get_headers(),
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"Successfully fetched {url}")
                        return content
                    
                    elif response.status == 429:
                        wait_time = 2 ** attempt * 60  # Exponential backoff
                        logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                    
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")
            
            except asyncio.TimeoutError:
                logger.error(f"Timeout for {url} (attempt {attempt + 1})")
            except aiohttp.ClientError as e:
                logger.error(f"Client error for {url}: {e} (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Unexpected error for {url}: {e} (attempt {attempt + 1})")
        
        self.blocked_domains.add(urlparse(url).netloc)
        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts")
        return None
    
    def _parse_duckduckgo(self, html: str, query: str) -> List[ScrapedResult]:
        """Parse DuckDuckGo search results"""
        results = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            for result in soup.find_all('div', class_='result'):
                try:
                    title_elem = result.find('a', class_='result__a')
                    snippet_elem = result.find('a', class_='result__snippet')
                    
                    if title_elem and snippet_elem:
                        title = title_elem.get_text().strip()
                        url = title_elem.get('href', '')
                        snippet = snippet_elem.get_text().strip()
                        
                        # Calculate relevance score
                        relevance = self._calculate_relevance(query, title, snippet)
                        
                        results.append(ScrapedResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            content='',
                            timestamp=datetime.now(),
                            source='DuckDuckGo',
                            relevance_score=relevance
                        ))
                
                except Exception as e:
                    logger.warning(f"Error parsing DuckDuckGo result: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error parsing DuckDuckGo HTML: {e}")
        
        return results
    
    def _parse_bing(self, html: str, query: str) -> List[ScrapedResult]:
        """Parse Bing search results"""
        results = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            for result in soup.find_all('li', class_='b_algo'):
                try:
                    title_elem = result.find('h2').find('a') if result.find('h2') else None
                    snippet_elem = result.find('p') or result.find('div', class_='b_caption')
                    
                    if title_elem and snippet_elem:
                        title = title_elem.get_text().strip()
                        url = title_elem.get('href', '')
                        snippet = snippet_elem.get_text().strip()
                        
                        relevance = self._calculate_relevance(query, title, snippet)
                        
                        results.append(ScrapedResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            content='',
                            timestamp=datetime.now(),
                            source='Bing',
                            relevance_score=relevance
                        ))
                
                except Exception as e:
                    logger.warning(f"Error parsing Bing result: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error parsing Bing HTML: {e}")
        
        return results
    
    def _parse_yahoo(self, html: str, query: str) -> List[ScrapedResult]:
        """Parse Yahoo search results"""
        results = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            for result in soup.find_all('div', class_='dd'):
                try:
                    title_elem = result.find('h3').find('a') if result.find('h3') else None
                    snippet_elem = result.find('span', class_='fz-ms')
                    
                    if title_elem and snippet_elem:
                        title = title_elem.get_text().strip()
                        url = title_elem.get('href', '')
                        snippet = snippet_elem.get_text().strip()
                        
                        relevance = self._calculate_relevance(query, title, snippet)
                        
                        results.append(ScrapedResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            content='',
                            timestamp=datetime.now(),
                            source='Yahoo',
                            relevance_score=relevance
                        ))
                
                except Exception as e:
                    logger.warning(f"Error parsing Yahoo result: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error parsing Yahoo HTML: {e}")
        
        return results
    
    def _calculate_relevance(self, query: str, title: str, snippet: str) -> float:
        """Calculate relevance score based on keyword matching"""
        query_words = set(query.lower().split())
        title_words = set(title.lower().split())
        snippet_words = set(snippet.lower().split())
        
        # Calculate intersection scores
        title_score = len(query_words.intersection(title_words)) / len(query_words) if query_words else 0
        snippet_score = len(query_words.intersection(snippet_words)) / len(query_words) if query_words else 0
        
        # Weight title matches higher
        return (title_score * 0.7) + (snippet_score * 0.3)
    
    async def scrape_page_content(self, session, url: str) -> str:
        """Scrape detailed content from a webpage"""
        try:
            html = await self.fetch_url(session, url)
            if not html:
                return ""
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text[:5000]  # Limit content length
        
        except Exception as e:
            logger.error(f"Error scraping content from {url}: {e}")
            return ""
    
    def cache_results(self, query: str, results: List[ScrapedResult]):
        """Cache results in database"""
        try:
            query_hash = hashlib.md5(query.encode()).hexdigest()
            cursor = self.db_conn.cursor()
            
            for result in results:
                cursor.execute(
                    '''
                    INSERT OR REPLACE INTO scraped_data 
                    (query_hash, title, url, snippet, content, source, timestamp, relevance_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (query_hash, result.title, result.url, result.snippet, 
                     result.content, result.source, result.timestamp, result.relevance_score)
                )
            
            self.db_conn.commit()
            logger.info(f"Cached {len(results)} results for query: {query}")
        
        except Exception as e:
            logger.error(f"Error caching results: {e}")
    
    def get_cached_results(self, query: str) -> List[ScrapedResult]:
        """Retrieve cached results from database"""
        try:
            query_hash = hashlib.md5(query.encode()).hexdigest()
            cursor = self.db_conn.cursor()
            
            cursor.execute(
                '''
                SELECT title, url, snippet, content, source, timestamp, relevance_score
                FROM scraped_data 
                WHERE query_hash = ? AND datetime(timestamp) > datetime('now', '-1 hour')
                ORDER BY relevance_score DESC
                ''',
                (query_hash,)
            )
            
            results = []
            for row in cursor.fetchall():
                results.append(ScrapedResult(
                    title=row[0],
                    url=row[1],
                    snippet=row[2],
                    content=row[3],
                    source=row[4],
                    timestamp=datetime.fromisoformat(row[5]),
                    relevance_score=row[6]
                ))
            
            if results:
                logger.info(f"Retrieved {len(results)} cached results for query: {query}")
            
            return results
        
        except Exception as e:
            logger.error(f"Error retrieving cached results: {e}")
            return []
    
    async def search(self, query: str, max_results: int = 20, use_cache: bool = True) -> List[ScrapedResult]:
        """Main search function that aggregates results from multiple search engines"""
        
        # Check cache first
        if use_cache:
            cached_results = self.get_cached_results(query)
            if cached_results:
                return cached_results[:max_results]
        
        all_results = []
        
        try:
            # Create aiohttp session
            async with aiohttp.ClientSession() as session:
                
                # Search all engines concurrently
                tasks = []
                for engine_name, engine_config in self.search_engines.items():
                    try:
                        url = engine_config['url']
                        params = {k: v.format(query=query) for k, v in engine_config['params'].items()}
                        
                        task = self.search_engine(session, engine_name, url, params, query)
                        tasks.append(task)
                        
                    except Exception as e:
                        logger.error(f"Error setting up search for {engine_name}: {e}")
                
                # Wait for all searches to complete
                results_lists = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Combine results
                for results in results_lists:
                    if isinstance(results, list):
                        all_results.extend(results)
                    elif isinstance(results, Exception):
                        logger.error(f"Search task failed: {results}")
                
                # Remove duplicates based on URL
                seen_urls = set()
                unique_results = []
                for result in all_results:
                    if result.url not in seen_urls:
                        seen_urls.add(result.url)
                        unique_results.append(result)
                
                # Sort by relevance score
                unique_results.sort(key=lambda x: x.relevance_score, reverse=True)
                
                # Limit results
                final_results = unique_results[:max_results]
                
                # Fetch detailed content for top results
                content_tasks = []
                for result in final_results[:5]:  # Only fetch content for top 5 results
                    content_tasks.append(
                        self.scrape_page_content(session, result.url)
                    )
                
                contents = await asyncio.gather(*content_tasks, return_exceptions=True)
                
                for i, content in enumerate(contents):
                    if isinstance(content, str) and i < len(final_results):
                        final_results[i].content = content
                
                # Cache results
                if final_results:
                    self.cache_results(query, final_results)
                
                logger.info(f"Search completed. Found {len(final_results)} results for: {query}")
                return final_results
        
        except Exception as e:
            logger.error(f"Error in main search function: {e}")
            return []
    
    async def search_engine(self, session, engine_name: str, url: str, params: dict, query: str) -> List[ScrapedResult]:
        """Search a specific search engine"""
        try:
            html = await self.fetch_url(session, url, params)
            if html:
                parser = self.search_engines[engine_name]['parser']
                results = parser(html, query)
                logger.info(f"Found {len(results)} results from {engine_name}")
                return results
            else:
                logger.warning(f"No HTML returned from {engine_name}")
                return []
        
        except Exception as e:
            logger.error(f"Error searching {engine_name}: {e}")
            return []
    
    def export_results(self, results: List[ScrapedResult], format: str = 'json') -> str:
        """Export results in different formats"""
        try:
            if format.lower() == 'json':
                data = []
                for result in results:
                    data.append({
                        'title': result.title,
                        'url': result.url,
                        'snippet': result.snippet,
                        'content': result.content[:500],  # Truncate content
                        'source': result.source,
                        'relevance_score': result.relevance_score,
                        'timestamp': result.timestamp.isoformat()
                    })
                return json.dumps(data, indent=2, ensure_ascii=False)
            
            elif format.lower() == 'csv':
                import csv
                import io
                
                output = io.StringIO()
                writer = csv.writer(output)
                
                # Write header
                writer.writerow(['Title', 'URL', 'Snippet', 'Content', 'Source', 'Relevance Score', 'Timestamp'])
                
                # Write data
                for result in results:
                    writer.writerow([
                        result.title,
                        result.url,
                        result.snippet,
                        result.content[:500],
                        result.source,
                        result.relevance_score,
                        result.timestamp.isoformat()
                    ])
                
                return output.getvalue()
            
            else:
                raise ValueError(f"Unsupported format: {format}")
        
        except Exception as e:
            logger.error(f"Error exporting results: {e}")
            return ""
    
    def __del__(self):
        """Cleanup database connection"""
        try:
            if hasattr(self, 'db_conn'):
                self.db_conn.close()
        except:
            pass

# Example usage
if __name__ == "__main__":
    async def main():
        scraper = OmniScraper()
        
        # Test search
        query = "Python web scraping techniques"
        results = await scraper.search(query, max_results=10)
        
        print(f"\nFound {len(results)} results for '{query}':\n")
        
        for i, result in enumerate(results, 1):
            print(f"{i}. {result.title}")
            print(f"   URL: {result.url}")
            print(f"   Source: {result.source}")
            print(f"   Relevance: {result.relevance_score:.2f}")
            print(f"   Snippet: {result.snippet[:100]}...")
            print()
        
        # Export results
        json_export = scraper.export_results(results, 'json')
        with open('search_results.json', 'w', encoding='utf-8') as f:
            f.write(json_export)
        
        print("Results exported to search_results.json")
    
    asyncio.run(main())