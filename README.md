# LinkedIn Profile Scraper

A powerful tool to scrape LinkedIn Recruiter search results and extract structured profile data into CSV format. This scraper uses a hybrid approach combining Playwright for search page navigation and the [linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server) for detailed profile data extraction.

## Features

- **Automated Search Scraping**: Extracts profile URLs from LinkedIn Recruiter search results with pagination support
- **MCP Integration**: Uses the Model Context Protocol for reliable profile data fetching
- **Comprehensive Data Extraction**: Extracts 13 key fields from each profile
- **Fuzzy School Matching**: Intelligently matches educational institutions against target schools
- **Rate Limiting**: Built-in delays (3-5 seconds) to avoid LinkedIn's anti-bot measures
- **Resume Capability**: Can resume interrupted scraping sessions
- **Batch Processing**: Saves progress periodically to prevent data loss
- **CSV Export**: Outputs data in clean CSV format with proper escaping

## Extracted Fields

For each profile, the scraper extracts:

1. **Name**: Full name from profile
2. **Job Titles at Target Companies**: All titles held at monmarché.fr, Prosol, or Grand Frais
3. **Total Years of Experience**: Sum of all professional experience (rounded to nearest 0.5 year)
4. **Years at Target Companies**: Experience duration at target companies
5. **Current Company**: Most recent employer
6. **LinkedIn Profile URL**: Direct link to the profile
7. **Schools Attended**: Complete list of educational institutions
8. **Target School**: Matched school from target list (INSEAD, HEC Paris, ESCP, etc.)
9. **Spoken Languages**: All languages listed on profile
10. **English Flag**: Set to "english" if English is listed
11. **City/Location**: Geographic location from profile
12. **Paris Flag**: Set to "Paris et périphérie" if in Paris area
13. **Years at Food Retailers**: Experience at Leclerc, Carrefour, Aldi, etc.

## Prerequisites

- **Python 3.10+**
- **LinkedIn Premium/Recruiter Account**: Required for accessing recruiter search
- **linkedin-mcp-server**: Must be installed and configured (see setup below)

## Installation

### 1. Clone the Repository

```bash
cd linkedin-profile-scraper
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```bash
playwright install chromium
```

### 5. Setup linkedin-mcp-server

The scraper requires the linkedin-mcp-server to be installed and configured:

```bash
# Install via uvx
uvx playwright install chromium

# First-time setup (interactive login)
uvx linkedin-scraper-mcp --get-session

# Follow the prompts to log in to LinkedIn
# Your session will be saved to ~/.linkedin-mcp/session.json
```

**Important**: Make sure you log in with your LinkedIn Premium/Recruiter account.

For more details, see the [linkedin-mcp-server documentation](https://github.com/stickerdaniel/linkedin-mcp-server).

## Configuration

The scraper uses three configuration files in the `config/` directory:

### target_schools.txt

List of target schools for fuzzy matching (one per line):
```
INSEAD
HEC Paris
ESCP Business School
EDHEC Business School
ESSEC Business School
emlyon business school
SKEMA Business School
Grenoble Ecole de Management
NEOMA Business School
Université Paris Dauphine – PSL
Audencia
```

### target_companies.txt

Companies to track for job titles and experience (one per line):
```
monmarché.fr
Prosol
Grand Frais
```

### food_retailers.txt

Other food retailers to track experience (one per line):
```
Leclerc
Galec
Intermarché
Mousquetaires
Lidl
Aldi
Carrefour
Metro
Auchan
Monoprix
```

You can edit these files to customize the matching criteria.

## Usage

### Basic Usage

```bash
cd src
python main.py --search-url "https://www.linkedin.com/recruiter/search/..." --output results.csv
```

### Advanced Options

```bash
# Custom delay between requests (5-7 seconds)
python main.py --search-url "..." --output results.csv --delay 5-7

# Limit to first 5 pages of search results
python main.py --search-url "..." --output results.csv --max-pages 5

# Resume interrupted scraping
python main.py --search-url "..." --output results.csv --resume

# Show browser window (non-headless mode)
python main.py --search-url "..." --output results.csv --no-headless

# Verbose logging
python main.py --search-url "..." --output results.csv --verbose

# Custom batch size (save progress every 25 profiles)
python main.py --search-url "..." --output results.csv --batch-size 25
```

### Getting the LinkedIn Recruiter Search URL

1. Log in to LinkedIn with your Recruiter account
2. Navigate to the Recruiter search interface
3. Configure your search filters (location, keywords, etc.)
4. Copy the URL from your browser's address bar
5. Use this URL with the `--search-url` parameter

**Example URL format:**
```
https://www.linkedin.com/recruiter/search/results?keywords=...
```

## How It Works

The scraper operates in 4 steps:

### Step 1: Extract Profile URLs
- Navigates to the LinkedIn Recruiter search URL using Playwright
- Scrolls through all search result pages
- Extracts unique profile URLs from each page
- Handles pagination automatically

### Step 2: Fetch Profile Data
- Connects to the linkedin-mcp-server via MCP
- Fetches detailed profile data for each URL
- Applies rate limiting (3-5 second random delays)
- Implements exponential backoff for retries

### Step 3: Extract & Calculate Fields
- Parses profile data structure
- Extracts all 13 required fields
- Calculates experience durations from dates
- Performs fuzzy matching for schools (85% threshold)
- Sets appropriate flags (English, Paris)

### Step 4: Export to CSV
- Formats data as CSV with proper escaping
- Saves to output file
- Prints results to console

## Output Format

The scraper generates a CSV file with the following columns (in order):

```csv
name,job_titles_at_target_companies,total_years_experience,years_at_target_companies,current_company,linkedin_url,schools_attended,target_school,spoken_languages,english_flag,city_location,paris_flag,years_at_food_retailers
```

Example output:
```csv
name,job_titles_at_target_companies,total_years_experience,years_at_target_companies,current_company,linkedin_url,schools_attended,target_school,spoken_languages,english_flag,city_location,paris_flag,years_at_food_retailers
John Doe,"Manager, Director",10.5,3.0,Grand Frais,https://www.linkedin.com/in/johndoe,"HEC Paris, University of Paris",HEC Paris,"French, English",english,"Paris, Île-de-France",Paris et périphérie,5.5
```

## Troubleshooting

### Authentication Issues

If you encounter authentication errors:

1. Ensure linkedin-mcp-server is properly configured:
   ```bash
   uvx linkedin-scraper-mcp --get-session
   ```

2. Verify your session is valid:
   ```bash
   ls -la ~/.linkedin-mcp/session.json
   ```

3. Try running in non-headless mode to see what's happening:
   ```bash
   python main.py --search-url "..." --output results.csv --no-headless
   ```

### Rate Limiting / Blocked

If LinkedIn blocks your requests:

1. Increase the delay between requests:
   ```bash
   python main.py --search-url "..." --output results.csv --delay 10-15
   ```

2. Process in smaller batches and wait between runs

3. Ensure you're using a recruiter account with proper permissions

### Empty Results

If no profiles are found:

1. Verify the search URL is correct and accessible
2. Check that you're logged in with the correct account
3. Try running in non-headless mode to debug
4. Check logs in `scraper.log` for detailed error messages

### Resume Not Working

If resume mode doesn't skip already-processed profiles:

1. Ensure the output filename matches exactly
2. Check that the CSV file exists in the output directory
3. Verify the CSV file has valid data with `linkedin_url` column

## Project Structure

```
linkedin-profile-scraper/
├── README.md                      # This file
├── .gitignore                     # Git ignore rules
├── requirements.txt               # Python dependencies
├── config/                        # Configuration files
│   ├── target_schools.txt         # Target schools for matching
│   ├── target_companies.txt       # Target companies to track
│   └── food_retailers.txt         # Food retailers for experience calculation
├── src/                           # Source code
│   ├── __init__.py
│   ├── main.py                    # CLI entry point
│   ├── search_scraper.py          # Playwright search scraper
│   ├── profile_processor.py       # MCP integration
│   ├── data_calculator.py         # Field extraction & calculations
│   └── csv_exporter.py            # CSV export functionality
├── output/                        # Output directory for CSV files
└── tests/                         # Unit tests
```

## Legal & Ethical Considerations

**IMPORTANT**: Web scraping may violate LinkedIn's Terms of Service. This tool is intended for:

- **Personal use only**
- **Authorized research purposes**
- **Legitimate business purposes with proper authorization**

**You are responsible for:**
- Complying with LinkedIn's Terms of Service
- Respecting user privacy and data protection laws (GDPR, etc.)
- Obtaining necessary permissions before scraping
- Using the data ethically and legally

The authors of this tool are not responsible for any misuse or legal consequences arising from its use.

## Rate Limiting Best Practices

To avoid being blocked by LinkedIn:

1. **Use conservative delays**: The default 3-5 second delay is recommended
2. **Don't run continuously**: Take breaks between scraping sessions
3. **Limit batch sizes**: Process reasonable numbers of profiles at a time
4. **Use a recruiter account**: Ensures proper access permissions
5. **Monitor for errors**: Stop if you see rate limiting errors

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is provided as-is for educational and research purposes. Use at your own risk.

## Acknowledgments

- [linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server) by stickerdaniel
- [Playwright](https://playwright.dev/) for browser automation
- [MCP (Model Context Protocol)](https://github.com/anthropics/anthropic-mcp) by Anthropic

## Support

For issues or questions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review logs in `scraper.log`
3. Open an issue on GitHub with:
   - Error message
   - Steps to reproduce
   - Python version and OS
   - Relevant log output

## Changelog

### v0.1.0 (Initial Release)
- Hybrid Playwright + MCP architecture
- Support for LinkedIn Recruiter search scraping
- Comprehensive field extraction (13 fields)
- Fuzzy school matching
- Rate limiting and resume capability
- CSV export with proper formatting
