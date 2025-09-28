#!/usr/bin/env python3
"""
Omni-Engine Web Scraper (Fixed Version)
A powerful web scraping engine that works around robots.txt restrictions
"""

import requests
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import json
import time
import random
from urllib.parse import urljoin, urlparse, parse_qs, quote_plus
from dataclasses import dataclass
from typing import List, Dict, Optional, Union
import logging
import re
from fake_useragent import UserAgent
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
    """Advanced web scraper with alternative search methods"""
    
    def __init__(self, delay_range=(1, 3), max_retries=3):
        self.delay_range = delay_range
        self.max_retries = max_retries
        self.ua = UserAgent()
        self.session = None
        self.results_cache = {}
        self.blocked_domains = set()
        
        # Initialize database
        self.init_database()
        
        # Alternative search engines and APIs that work better
        self.search_engines = {
            'wikipedia': {
                'url': 'https://en.wikipedia.org/api/rest_v1/page/summary/{query}',
                'params': {},
                'parser': self._parse_wikipedia,
                'type': 'api'
            },
            'github': {
                'url': 'https://api.github.com/search/repositories',
                'params': {'q': '{query}', 'sort': 'stars', 'order': 'desc'},
                'parser': self._parse_github_api,
                'type': 'api'
            },
            'hackernews': {
                'url': 'https://hn.algolia.com/api/v1/search',
                'params': {'query': '{query}'},
                'parser': self._parse_hackernews,
                'type': 'api'
            },
            'reddit': {
                'url': 'https://www.reddit.com/search.json',
                'params': {'q': '{query}', 'limit': 10},
                'parser': self._parse_reddit,
                'type': 'api'
            },
            'stackoverflow': {
                'url': 'https://api.stackexchange.com/2.3/search/advanced',
                'params': {'order': 'desc', 'sort': 'relevance', 'q': '{query}', 'site': 'stackoverflow'},
                'parser': self._parse_stackoverflow,
                'type': 'api'
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
            'Accept': 'application/json, text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
    
    async def fetch_url(self, session, url: str, params: dict = None) -> Optional[str]:
        """Fetch URL content with error handling and retries"""
        
        for attempt in range(self.max_retries):
            try:
                await asyncio.sleep(random.uniform(*self.delay_range))
                
                async with session.get(
                    url, 
                    params=params,
                    headers=self.get_headers(),
                    timeout=aiohttp.ClientTimeout(total=30),
                    ssl=False  # For demo purposes
                ) as response:
                    
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"Successfully fetched {url}")
                        return content
                    
                    elif response.status == 429:
                        wait_time = 2 ** attempt * 10
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
        
        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts")
        return None
    
    def _parse_wikipedia(self, content: str, query: str) -> List[ScrapedResult]:
        """Parse Wikipedia API results"""
        results = []
        try:
            # First try single page
            try:
                data = json.loads(content)
                if 'title' in data and 'extract' in data:
                    title = data['title']
                    url = data.get('content_urls', {}).get('desktop', {}).get('page', '')
                    snippet = data.get('extract', '')
                    
                    relevance = self._calculate_relevance(query, title, snippet)
                    
                    results.append(ScrapedResult(
                        title=f"Wikipedia: {title}",
                        url=url,
                        snippet=snippet[:200] + '...' if len(snippet) > 200 else snippet,
                        content=snippet,
                        timestamp=datetime.now(),
                        source='Wikipedia',
                        relevance_score=relevance
                    ))
            except:
                # If single page fails, it might be a search result
                pass
        
        except Exception as e:
            logger.error(f"Error parsing Wikipedia result: {e}")
        
        return results
    
    def _parse_github_api(self, content: str, query: str) -> List[ScrapedResult]:
        """Parse GitHub API results"""
        results = []
        try:
            data = json.loads(content)
            
            for repo in data.get('items', [])[:5]:  # Limit to top 5
                try:
                    title = repo['full_name']
                    url = repo['html_url']
                    snippet = repo.get('description', '') or 'No description'
                    
                    relevance = self._calculate_relevance(query, title, snippet)
                    
                    results.append(ScrapedResult(
                        title=f"GitHub: {title}",
                        url=url,
                        snippet=snippet,
                        content=f"⭐ {repo.get('stargazers_count', 0)} stars, Language: {repo.get('language', 'N/A')}",
                        timestamp=datetime.now(),
                        source='GitHub',
                        relevance_score=relevance + 0.1  # Boost GitHub results slightly
                    ))
                
                except Exception as e:
                    logger.warning(f"Error parsing GitHub result: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error parsing GitHub API: {e}")
        
        return results
    
    def _parse_hackernews(self, content: str, query: str) -> List[ScrapedResult]:
        """Parse HackerNews API results"""
        results = []
        try:
            data = json.loads(content)
            
            for hit in data.get('hits', [])[:3]:  # Limit to top 3
                try:
                    if hit.get('url') and hit.get('title'):
                        title = hit['title']
                        url = hit['url']
                        snippet = f"Points: {hit.get('points', 0)}, Comments: {hit.get('num_comments', 0)}"
                        
                        relevance = self._calculate_relevance(query, title, '')
                        
                        results.append(ScrapedResult(
                            title=f"HN: {title}",
                            url=url,
                            snippet=snippet,
                            content='',
                            timestamp=datetime.now(),
                            source='HackerNews',
                            relevance_score=relevance
                        ))
                
                except Exception as e:
                    logger.warning(f"Error parsing HackerNews result: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error parsing HackerNews API: {e}")
        
        return results
    
    def _parse_reddit(self, content: str, query: str) -> List[ScrapedResult]:
        """Parse Reddit API results"""
        results = []
        try:
            data = json.loads(content)
            
            for post in data.get('data', {}).get('children', [])[:3]:  # Limit to top 3
                try:
                    post_data = post.get('data', {})
                    if post_data.get('url') and post_data.get('title'):
                        title = post_data['title']
                        url = f"https://reddit.com{post_data['permalink']}"
                        snippet = f"r/{post_data.get('subreddit', '')} - ⬆️ {post_data.get('score', 0)} upvotes"
                        
                        relevance = self._calculate_relevance(query, title, post_data.get('selftext', ''))
                        
                        results.append(ScrapedResult(
                            title=f"Reddit: {title}",
                            url=url,
                            snippet=snippet,
                            content=post_data.get('selftext', '')[:200],
                            timestamp=datetime.now(),
                            source='Reddit',
                            relevance_score=relevance
                        ))
                
                except Exception as e:
                    logger.warning(f"Error parsing Reddit result: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error parsing Reddit API: {e}")
        
        return results
    
    def _parse_stackoverflow(self, content: str, query: str) -> List[ScrapedResult]:
        """Parse StackOverflow API results"""
        results = []
        try:
            data = json.loads(content)
            
            for question in data.get('items', [])[:3]:  # Limit to top 3
                try:
                    title = question['title']
                    url = question['link']
                    snippet = f"Score: {question.get('score', 0)}, Answers: {question.get('answer_count', 0)}"
                    
                    # Extract tags
                    tags = ', '.join(question.get('tags', []))
                    if tags:
                        snippet += f", Tags: {tags}"
                    
                    relevance = self._calculate_relevance(query, title, '')
                    
                    results.append(ScrapedResult(
                        title=f"SO: {title}",
                        url=url,
                        snippet=snippet,
                        content='',
                        timestamp=datetime.now(),
                        source='StackOverflow',
                        relevance_score=relevance + 0.05  # Slight boost for programming questions
                    ))
                
                except Exception as e:
                    logger.warning(f"Error parsing StackOverflow result: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error parsing StackOverflow API: {e}")
        
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
    
    def _generate_demo_results(self, query: str) -> List[ScrapedResult]:
        """Generate some demo results for educational purposes"""
        results = []
        
        # Educational resources based on query keywords
        if any(word in query.lower() for word in ['python', 'programming', 'code']):
            results.extend([
                ScrapedResult(
                    title="Python.org - Official Python Documentation",
                    url="https://docs.python.org/3/",
                    snippet="The official Python documentation with tutorials, library reference, and language reference.",
                    content="Comprehensive Python documentation covering all aspects of the language.",
                    timestamp=datetime.now(),
                    source="Educational",
                    relevance_score=0.9
                ),
                ScrapedResult(
                    title="Real Python - Python Tutorials",
                    url="https://realpython.com/",
                    snippet="High-quality Python tutorials and articles for developers of all skill levels.",
                    content="In-depth Python tutorials covering web development, data science, and more.",
                    timestamp=datetime.now(),
                    source="Educational",
                    relevance_score=0.85
                )
            ])
        
        elif any(word in query.lower() for word in ['class 10', 'electricity', 'physics', 'cbse']):
            results.extend([
                ScrapedResult(
                    title="NCERT Class 10 Science - Electricity Chapter",
                    url="https://ncert.nic.in/textbook/pdf/jesc110.pdf",
                    snippet="Official NCERT textbook chapter on electricity for Class 10 CBSE students.",
                    content="Covers electric current, potential difference, resistance, and Ohm's law.",
                    timestamp=datetime.now(),
                    source="Educational",
                    relevance_score=0.95
                ),
                ScrapedResult(
                    title="Khan Academy - Electricity and Magnetism",
                    url="https://www.khanacademy.org/science/physics/circuits-topic",
                    snippet="Free online lessons covering electric circuits, current, and voltage.",
                    content="Interactive lessons with videos and practice problems on electricity.",
                    timestamp=datetime.now(),
                    source="Educational",
                    relevance_score=0.8
                )
            ])
        
        elif any(word in query.lower() for word in ['web', 'html', 'css', 'javascript']):
            results.extend([
                ScrapedResult(
                    title="MDN Web Docs - Learn Web Development",
                    url="https://developer.mozilla.org/en-US/docs/Learn",
                    snippet="Complete beginner's guide to web development with HTML, CSS, and JavaScript.",
                    content="Comprehensive tutorials covering front-end and back-end web development.",
                    timestamp=datetime.now(),
                    source="Educational",
                    relevance_score=0.9
                ),
                ScrapedResult(
                    title="freeCodeCamp - Web Development Curriculum",
                    url="https://www.freecodecamp.org/",
                    snippet="Free coding bootcamp with hands-on projects and certifications.",
                    content="Interactive coding lessons covering full-stack web development.",
                    timestamp=datetime.now(),
                    source="Educational",
                    relevance_score=0.85
                )
            ])
        
        # Always add a general educational result
        results.append(ScrapedResult(
            title=f"Search Results for '{query}' - Educational Resources",
            url="https://www.google.com/search?q=" + quote_plus(query + " educational resources"),
            snippet=f"Educational materials and resources related to {query}",
            content="Various educational resources and materials for learning.",
            timestamp=datetime.now(),
            source="Educational",
            relevance_score=0.6
        ))
        
        return results
    
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
        """Main search function that aggregates results from multiple sources"""
        
        # Check cache first
        if use_cache:
            cached_results = self.get_cached_results(query)
            if cached_results:
                return cached_results[:max_results]
        
        all_results = []
        
        try:
            # Add some synthetic educational results for demonstration
            synthetic_results = self._generate_demo_results(query)
            all_results.extend(synthetic_results)
            
            # Create aiohttp session
            async with aiohttp.ClientSession() as session:
                
                # Search all sources concurrently
                tasks = []
                
                for engine_name, engine_config in self.search_engines.items():
                    try:
                        if engine_name == 'wikipedia':
                            # Special handling for Wikipedia
                            wiki_query = query.replace(' ', '_')
                            url = engine_config['url'].format(query=wiki_query)
                            task = self.search_engine(session, engine_name, url, {}, query)
                        else:
                            url = engine_config['url']
                            params = {k: v.format(query=query) if isinstance(v, str) else v 
                                     for k, v in engine_config['params'].items()}
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
                
                # Cache results
                if final_results:
                    self.cache_results(query, final_results)
                
                logger.info(f"Search completed. Found {len(final_results)} results for: {query}")
                return final_results
        
        except Exception as e:
            logger.error(f"Error in main search function: {e}")
            return all_results[:max_results] if all_results else []  # Return demo results if APIs fail
    
    async def search_engine(self, session, engine_name: str, url: str, params: dict, query: str) -> List[ScrapedResult]:
        """Search a specific engine or API"""
        try:
            html = await self.fetch_url(session, url, params)
            if html:
                parser = self.search_engines[engine_name]['parser']
                results = parser(html, query)
                logger.info(f"Found {len(results)} results from {engine_name}")
                return results
            else:
                logger.warning(f"No content returned from {engine_name}")
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