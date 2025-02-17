import asyncio
import os
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from supabase import create_client, Client
from openai import OpenAI
import json
from bs4 import BeautifulSoup

# Load environment variables
load_dotenv()

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_KEY')
)

def extract_report_content(html_content: str) -> str:
    """Extract only the relevant ski report content using CSS selector."""
    soup = BeautifulSoup(html_content, 'html.parser')
    report_div = soup.select_one("#__next > div.container-xl.content-container > div.styles_layout__Zkjid.layout-container > div > div.skireport_reportContent__Gmrl5")
    if report_div:
        return report_div.get_text(strip=True, separator=' ')
    return html_content  # Fallback to full content if selector not found

async def extract_snow_info_batch(urls: List[str], html_contents: List[str]) -> List[Dict]:
    """Extract snow information using GPT-4 for a batch of pages."""
    try:
        # Create prompts for each URL
        prompts = []
        for url, html in zip(urls, html_contents):
            # Extract only the relevant content using CSS selector
            report_content = extract_report_content(html)
            prompt = f"""Extract the following information from this ski resort webpage content. Return numbers for snowfall and snow depth (convert text numbers to digits), but keep lifts and runs as text. Return null if not found.

1. Resort Name (text)
2. Past Snowfall (in inches, for last 6 days)
3. Forecasted Snowfall (in inches, for next 6 days)
4. Mid Mountain Snow Depth (in inches)
5. Number of Lifts Open (keep as text, e.g. "5/8 Lifts Open")
6. Number of Runs Open (keep as text, e.g. "20/35 Runs Open")

Content: {report_content}

Format your response as a JSON object with these exact keys:
{{
    "Ski Resort": "name",
    "Snowfall 6 days ago": number,
    "Snowfall 5 days ago": number,
    "Snowfall 4 days ago": number,
    "Snowfall 3 days ago": number,
    "Snowfall 2 days ago": number,
    "Snowfall 1 day ago": number,
    "Snowfall forecasted today": number,
    "Snowfall forecasted in 1 day": number,
    "Snowfall forecasted in 2 days": number,
    "Snowfall forecasted in 3 days": number,
    "Snowfall forecasted in 4 days": number,
    "Snowfall forecasted in 5 days": number,
    "Mid Mountain Snow": number,
    "Lifts Open": "text",
    "Runs Open": "text"
}}
Use null for any missing values. Convert snow measurements to integers, but keep lifts and runs as text."""
            prompts.append(prompt)

        # Process prompts in parallel
        tasks = []
        for prompt in prompts:
            task = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts ski resort information from webpage content."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            tasks.append(task)
        
        # Wait for all OpenAI responses
        responses = await asyncio.gather(*[asyncio.to_thread(lambda t=t: t) for t in tasks])
        
        # Process responses
        results = []
        for url, response in zip(urls, responses):
            try:
                data = json.loads(response.choices[0].message.content)
                results.append({"url": url, "data": data})
            except Exception as e:
                print(f"Error processing GPT response for {url}: {str(e)}")
                results.append({"url": url, "data": None})
        
        return results
    except Exception as e:
        print(f"Error in batch extraction: {str(e)}")
        return [{"url": url, "data": None} for url in urls]

async def process_batch(urls: List[str], browser_config: BrowserConfig, run_config: CrawlerRunConfig):
    """Process a batch of URLs concurrently."""
    async with AsyncWebCrawler(config=browser_config) as crawler:
        tasks = []
        for url in urls:
            task = crawler.arun(url=url, config=run_config)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect successful results
        successful_urls = []
        successful_html = []
        failed_results = []
        
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                print(f"Failed to crawl {url}: {str(result)}")
                failed_results.append({"url": url, "data": None})
            elif result.success:
                successful_urls.append(url)
                successful_html.append(result.html)
                print(f"Successfully crawled {url}")
            else:
                print(f"Failed to crawl {url}: {result.error_message}")
                failed_results.append({"url": url, "data": None})
        
        # Process successful results in batches of 3
        all_extracted = []
        gpt_batch_size = 3
        
        for i in range(0, len(successful_urls), gpt_batch_size):
            batch_urls = successful_urls[i:i + gpt_batch_size]
            batch_html = successful_html[i:i + gpt_batch_size]
            
            # Extract information using GPT-4
            extracted_data = await extract_snow_info_batch(batch_urls, batch_html)
            all_extracted.extend(extracted_data)
            
            # Add a small delay between GPT batches
            if i + gpt_batch_size < len(successful_urls):
                await asyncio.sleep(1)
        
        # Combine successful and failed results
        all_extracted.extend(failed_results)
        return all_extracted

async def save_batch_to_supabase(results: List[Dict]):
    """Save batch results to Supabase, handling duplicates by deleting existing entries first."""
    for result in results:
        if result['data'] and result['data']['Ski Resort']:
            try:
                # First, delete any existing entries for this resort
                supabase.table('onthesnow')\
                    .delete()\
                    .eq('Ski Resort', result['data']['Ski Resort'])\
                    .execute()
                
                # Then insert the new data
                supabase.table('onthesnow')\
                    .insert(result['data'])\
                    .execute()
                
                print(f"Successfully saved data for {result['data']['Ski Resort']}")
            except Exception as e:
                print(f"Error saving to Supabase for {result['url']}: {str(e)}")
                # Print the full error details for debugging
                print(f"Full error details: {e}")
                print(f"Data being saved: {result['data']}")

async def main():
    # Read URLs from USACANADA.txt
    with open('USACANADA.txt', 'r') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    # Configure browser with minimal settings
    browser_config = BrowserConfig(
        headless=True,
        verbose=False
    )
    
    # Configure run settings with just cache mode
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS
    )
    
    # Process URLs in batches of 3
    batch_size = 3
    total_batches = (len(urls) + batch_size - 1) // batch_size
    
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i + batch_size]
        print(f"\nProcessing batch {i//batch_size + 1} of {total_batches}")
        
        # Process batch in parallel
        batch_results = await process_batch(batch, browser_config, run_config)
        
        # Save batch results to Supabase
        await save_batch_to_supabase(batch_results)
        print(f"Completed batch {i//batch_size + 1}")
        
        # Add a small delay between batches
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main()) 