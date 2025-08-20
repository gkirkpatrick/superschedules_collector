"""
Pagination failure logging system.

Logs sites where pagination detection failed for later analysis and improvement.
"""

import json
import os
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

class PaginationFailureLogger:
    """Logs pagination detection failures for analysis."""
    
    def __init__(self, log_file: str = "pagination_failures.jsonl"):
        self.log_file = log_file
        
    def log_failure(self, url: str, html_content: str, context: Optional[Dict[str, Any]] = None):
        """
        Log a pagination detection failure.
        
        Args:
            url: The URL where pagination detection failed
            html_content: The HTML content of the page
            context: Additional context (attempted strategies, etc.)
        """
        try:
            # Create content hash to avoid duplicate logging
            content_hash = hashlib.md5(html_content.encode('utf-8')).hexdigest()[:12]
            
            # Extract domain for grouping
            domain = urlparse(url).netloc
            
            # Create failure record
            failure_record = {
                "timestamp": datetime.now().isoformat(),
                "url": url,
                "domain": domain,
                "content_hash": content_hash,
                "content_length": len(html_content),
                "context": context or {},
                "html_sample": self._extract_html_sample(html_content),
                "potential_pagination_indicators": self._extract_pagination_hints(html_content)
            }
            
            # Check if we've already logged this failure
            if self._is_duplicate_failure(url, content_hash):
                logger.debug(f"Skipping duplicate pagination failure for {url}")
                return
                
            # Write to log file
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(failure_record) + '\n')
                
            logger.info(f"Logged pagination failure: {domain} -> {self.log_file}")
            
        except Exception as e:
            logger.error(f"Failed to log pagination failure for {url}: {e}")
            
    def _extract_html_sample(self, html_content: str) -> Dict[str, Any]:
        """Extract a useful sample of HTML for analysis."""
        from bs4 import BeautifulSoup
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract key elements that might contain pagination
            sample = {
                "title": soup.title.string if soup.title else None,
                "navigation_links": [],
                "potential_pagination_elements": [],
                "javascript_hints": []
            }
            
            # Get navigation-related links
            nav_links = []
            for link in soup.find_all('a', href=True)[:20]:  # First 20 links
                text = link.get_text(strip=True)
                href = link.get('href')
                classes = ' '.join(link.get('class', []))
                
                if any(word in text.lower() or word in href.lower() or word in classes.lower() 
                       for word in ['next', 'more', 'page', 'calendar', 'month']):
                    nav_links.append({
                        'text': text[:50],  # Limit text length
                        'href': href,
                        'classes': classes
                    })
                    
            sample['navigation_links'] = nav_links
            
            # Look for pagination-related elements
            pagination_selectors = [
                '.pagination', '.pager', '.page-nav', '.calendar-nav',
                '.next', '.more', '.load-more', '[data-page]'
            ]
            
            for selector in pagination_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    sample['potential_pagination_elements'].append({
                        'tag': elem.name,
                        'classes': elem.get('class', []),
                        'text': elem.get_text(strip=True)[:100]
                    })
                    
            # Extract JavaScript hints
            scripts = soup.find_all('script')
            for script in scripts[:5]:  # First 5 scripts
                if script.string:
                    script_content = script.string
                    if any(hint in script_content.lower() for hint in ['page', 'pagination', 'calendar', 'next']):
                        # Extract relevant lines
                        lines = script_content.split('\n')
                        relevant_lines = []
                        for line in lines:
                            if any(hint in line.lower() for hint in ['page', 'pagination', 'next', 'calendar']):
                                relevant_lines.append(line.strip()[:100])
                                if len(relevant_lines) >= 3:  # Limit to 3 lines
                                    break
                        if relevant_lines:
                            sample['javascript_hints'].extend(relevant_lines)
                            
            return sample
            
        except Exception as e:
            logger.warning(f"Failed to extract HTML sample: {e}")
            return {"error": str(e)}
            
    def _extract_pagination_hints(self, html_content: str) -> Dict[str, Any]:
        """Extract potential pagination indicators for LLM analysis."""
        hints = {
            "has_numbered_links": False,
            "has_next_prev_text": False,
            "has_javascript_calendar": False,
            "has_load_more_buttons": False,
            "url_patterns": []
        }
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Check for numbered links
            for link in soup.find_all('a', href=True):
                text = link.get_text(strip=True)
                if text.isdigit():
                    hints["has_numbered_links"] = True
                    break
                    
            # Check for next/prev text
            if any(word in html_content.lower() for word in ['next', 'previous', 'more events', 'load more']):
                hints["has_next_prev_text"] = True
                
            # Check for JavaScript calendar frameworks
            if any(framework in html_content.lower() for framework in ['fullcalendar', 'calendar.js', 'datepicker']):
                hints["has_javascript_calendar"] = True
                
            # Check for load more buttons
            load_more_selectors = ['.load-more', '.show-more', '[data-load-more]', 'button:contains("more")']
            for selector in load_more_selectors:
                if soup.select(selector):
                    hints["has_load_more_buttons"] = True
                    break
                    
            # Extract URL patterns that might suggest pagination
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                # Look for patterns like /page/2, ?page=2, /2, /calendar/2024/01
                if any(pattern in href for pattern in ['/page/', '?page=', '/calendar/', '/events/']):
                    hints["url_patterns"].append(href)
                    
            # Limit URL patterns to avoid huge logs
            hints["url_patterns"] = hints["url_patterns"][:10]
                    
        except Exception as e:
            logger.warning(f"Failed to extract pagination hints: {e}")
            hints["extraction_error"] = str(e)
            
        return hints
        
    def _is_duplicate_failure(self, url: str, content_hash: str) -> bool:
        """Check if we've already logged this failure recently."""
        if not os.path.exists(self.log_file):
            return False
            
        try:
            # Check last 100 entries to avoid reading huge files
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                recent_lines = lines[-100:] if len(lines) > 100 else lines
                
            for line in recent_lines:
                try:
                    record = json.loads(line.strip())
                    if record.get('url') == url and record.get('content_hash') == content_hash:
                        return True
                except json.JSONDecodeError:
                    continue
                    
        except Exception as e:
            logger.warning(f"Error checking for duplicate failures: {e}")
            
        return False
        
    def get_failure_summary(self) -> Dict[str, Any]:
        """Get a summary of logged failures."""
        if not os.path.exists(self.log_file):
            return {"total_failures": 0, "domains": {}}
            
        domain_failures = {}
        total_failures = 0
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        domain = record.get('domain', 'unknown')
                        
                        if domain not in domain_failures:
                            domain_failures[domain] = {
                                'count': 0,
                                'urls': [],
                                'latest_failure': None
                            }
                            
                        domain_failures[domain]['count'] += 1
                        domain_failures[domain]['latest_failure'] = record.get('timestamp')
                        
                        if record.get('url') not in domain_failures[domain]['urls']:
                            domain_failures[domain]['urls'].append(record.get('url'))
                            
                        total_failures += 1
                        
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            logger.error(f"Error generating failure summary: {e}")
            
        return {
            "total_failures": total_failures,
            "unique_domains": len(domain_failures),
            "domains": domain_failures
        }
        

def log_pagination_failure(url: str, html_content: str, context: Optional[Dict[str, Any]] = None, log_file: str = "pagination_failures.jsonl"):
    """
    Convenience function to log a pagination failure.
    
    Args:
        url: URL where pagination detection failed
        html_content: HTML content of the page
        context: Additional context about the failure
        log_file: Log file path
    """
    logger_instance = PaginationFailureLogger(log_file)
    logger_instance.log_failure(url, html_content, context)