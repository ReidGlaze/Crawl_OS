# OnTheSnow Ski Resort Data Crawler

This project crawls OnTheSnow.com to collect ski resort data including snowfall history, forecasts, and operational status for resorts across the US and Canada. The data is stored in a Supabase database for easy access and analysis.

## Setup Instructions

### 1. Environment Setup

1. Clone this repository to your local machine
2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment:
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
4. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

### 2. Environment Variables

1. Copy the `env.example` file to create a new `.env` file:
   ```bash
   cp env.example .env
   ```
2. Open `.env` and fill in your credentials:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_SERVICE_KEY`: Your Supabase service role key
   - `LLM_MODEL`: The OpenAI model to use (e.g., "gpt-4o-mini")

### 3. Supabase Setup

1. Create a new table in your Supabase project named `onthesnow` with the following columns:
   ```sql
   create table onthesnow (
     "Ski Resort" text primary key,
     "Snowfall 6 days ago" integer,
     "Snowfall 5 days ago" integer,
     "Snowfall 4 days ago" integer,
     "Snowfall 3 days ago" integer,
     "Snowfall 2 days ago" integer,
     "Snowfall 1 day ago" integer,
     "Snowfall forecasted today" integer,
     "Snowfall forecasted in 1 day" integer,
     "Snowfall forecasted in 2 days" integer,
     "Snowfall forecasted in 3 days" integer,
     "Snowfall forecasted in 4 days" integer,
     "Snowfall forecasted in 5 days" integer,
     "Mid Mountain Snow" integer,
     "Lifts Open" text,
     "Runs Open" text
   );
   ```

## Running the Crawler

1. Ensure your virtual environment is activated
2. Run the crawler:
   ```bash
   python crawl.py
   ```

The crawler will process all URLs in `USACANADA.txt` in batches of 3 resorts at a time.

## How It Works

1. **URL Processing**: The script reads resort URLs from `USACANADA.txt`

2. **Web Crawling**: Using `Crawl4ai`, the script visits each resort's page and collects the HTML content

3. **Data Extraction**: 
   - The script uses BeautifulSoup to extract the relevant report content from the HTML
   - GPT-4 processes the content to extract specific data points (snowfall history, forecasts, etc.)
   - Data is formatted into a structured JSON format

4. **Data Storage**:
   - For each resort, existing data is deleted from the Supabase table
   - New data is inserted into the table
   - This ensures the data stays current without duplicates

5. **Batch Processing**:
   - URLs are processed in batches of 3 to manage rate limits and resources
   - Small delays are added between batches to prevent overwhelming the servers

## Error Handling

- The script includes robust error handling for both crawling and data processing
- Failed crawls are logged but don't stop the entire process
- Invalid data is skipped with appropriate error messages

## Data Updates

The script can be run regularly to keep the data current. Each run will:
- Delete old data for each resort
- Insert new data
- Maintain a clean, up-to-date database of ski resort conditions 
