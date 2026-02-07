# LinkedIn Profile Scraper - RapidAPI Setup Guide

This guide explains how to use the RapidAPI-based LinkedIn profile scraper.

## 1. Get Your RapidAPI Key

### Sign Up and Subscribe

1. **Visit the API page**: https://rapidapi.com/liscraper-liscraper-default/api/li-data-scraper

2. **Create account** (if you don't have one):
   - Click "Sign Up" in the top right
   - Use email or social login

3. **Subscribe to the API**:
   - Click "Subscribe to Test"
   - Choose a plan:
     - **Basic** (FREE): 50 requests/month - good for testing
     - **Pro** ($10/month): 500 requests/month
     - **Ultra** ($45/month): 4,500 requests/month
     - **Mega** ($200/month): 100,000 requests/month

4. **Get your API key**:
   - After subscribing, you'll see your API key in the header section
   - Copy the `x-rapidapi-key` value
   - Keep this key private!

## 2. Prepare Your Input CSV

Create a CSV file with LinkedIn profile URLs:

```csv
Profile_Name,Profile_Link
John Doe,https://www.linkedin.com/in/johndoe
Jane Smith,https://www.linkedin.com/in/janesmith
```

**Required column**: `Profile_Link`

**Note**: Use standard LinkedIn URLs (`/in/username`), not recruiter URLs (`/talent/profile/...`)

## 3. Run the Scraper

### Option A: Set API Key as Environment Variable (Recommended)

```bash
export RAPIDAPI_KEY="your-api-key-here"
python src/fetch_profiles_rapidapi.py --input input_profiles.csv --output results.csv
```

### Option B: Pass API Key as Argument

```bash
python src/fetch_profiles_rapidapi.py \
  --input input_profiles.csv \
  --output results.csv \
  --api-key "your-api-key-here"
```

### Optional Parameters

```bash
python src/fetch_profiles_rapidapi.py \
  --input input_profiles.csv \
  --output results.csv \
  --api-key "your-key" \
  --delay 1.5 \              # Seconds between requests (default: 1.0)
  --config-dir config \      # Configuration directory (default: config)
  --output-dir output        # Output directory (default: output)
```

## 4. Output

The script will generate a CSV with these 13 fields:

1. `name` - Full name
2. `job_titles_at_target_companies` - Job titles at monmarché.fr, Prosol, or Grand Frais
3. `total_years_experience` - Total years of work experience
4. `years_at_target_companies` - Years at target companies
5. `current_company` - Current employer
6. `linkedin_url` - Profile URL
7. `schools_attended` - All schools attended
8. `target_school` - Matched target school (INSEAD, HEC, ESCP, etc.)
9. `spoken_languages` - Languages spoken
10. `english_flag` - "english" if English is listed
11. `city_location` - City/location
12. `paris_flag` - "Paris et périphérie" if in Paris area
13. `years_at_food_retailers` - Years at Leclerc, Carrefour, Aldi, etc.

## 5. Rate Limits

**Important**: Respect rate limits based on your plan:

- **Basic** (FREE): 50 requests/month, 5 requests/minute
- **Pro** ($10/month): 500 requests/month, 60 requests/minute
- **Ultra** ($45/month): 4,500 requests/month, 120 requests/minute
- **Mega** ($200/month): 100,000 requests/month, 500 requests/minute

The script includes a `--delay` parameter (default 1 second) to control request rate.

## 6. Monitoring and Debugging

- **Logs**: Check `rapidapi_processing.log` for detailed logs
- **Debug output**: First profile's raw data is saved to `/tmp/rapidapi_profile_debug.json`
- **Success rate**: Displayed at the end of processing

## 7. Cost Estimation

### Example: 88 Profiles

With the **Basic FREE plan** (50 requests/month):
- Can process 50 profiles/month
- Need 2 months for 88 profiles
- **Cost**: FREE

With the **Pro plan** ($10/month):
- Can process 500 profiles/month
- Process all 88 in one run
- **Cost**: $10 one-time

### Recommendation

Start with the **FREE Basic plan** to test with 1-2 profiles, then upgrade to Pro ($10) if the data quality meets your needs.

## 8. Troubleshooting

### "Rate limit exceeded" error
- You've hit your monthly/minute limit
- Wait for the limit to reset or upgrade your plan

### "HTTP 401" or "Unauthorized"
- Check your API key is correct
- Ensure you're subscribed to the API

### "HTTP 404" or "Profile not found"
- The LinkedIn URL may be invalid
- Profile might be private or deleted
- Try with a different profile URL

### Empty fields in output
- Some profiles may not have all data public
- Check `/tmp/rapidapi_profile_debug.json` to see raw API response
- The API may have limitations on what data it can access

## 9. Next Steps

After successful test:
1. Process your full list of 88 profiles
2. Review the output CSV
3. Adjust target companies/schools in `config/` files if needed
4. Run again with updated configuration

## Support

- **RapidAPI Support**: https://rapidapi.com/freshdata-freshdata-default/api/fresh-linkedin-profile-data/discussions
- **API Documentation**: Check the "Endpoints" tab on the RapidAPI page
