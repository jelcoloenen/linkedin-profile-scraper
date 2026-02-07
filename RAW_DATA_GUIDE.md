# Raw Data Storage & Reprocessing Guide

## Overview

This project saves ALL raw API responses from RapidAPI so you can reprocess profiles later without making new API calls. This is crucial because:

1. **Save API Credits**: Each API call costs money/credits. By saving raw data, you only need to fetch once.
2. **Experiment Freely**: Change extraction logic, target companies, schools, etc. without re-scraping.
3. **Debug Issues**: If extraction fails, you have the original data to debug.
4. **Future Flexibility**: Add new fields later by reprocessing saved data.

## How Raw Data is Stored

### Automatic Storage

By default, when you run `fetch_profiles_rapidapi.py`, raw API responses are automatically saved to:

```
output/
└── raw_data/
    ├── profile_001.json        # Individual profile files
    ├── profile_002.json
    ├── profile_003.json
    ├── ...
    └── all_profiles_raw.json   # Combined file with all profiles
```

### What's Stored

Each file contains:
- **URL**: The LinkedIn profile URL
- **raw_data**: The complete API response with all fields (experiences, educations, skills, languages, etc.)
- **success**: Whether the API call succeeded
- **error**: Error message if it failed

### Storage Format

**Individual files** (`profile_001.json`):
```json
{
  "url": "https://www.linkedin.com/in/johndoe",
  "raw_data": {
    "data": {
      "full_name": "John Doe",
      "company": "Current Company",
      "location": "Paris, France",
      "experiences": [...],
      "educations": [...],
      "languages": [...],
      "skills": "..."
    }
  },
  "success": true
}
```

**Combined file** (`all_profiles_raw.json`):
```json
[
  { "url": "...", "raw_data": {...}, "success": true },
  { "url": "...", "raw_data": {...}, "success": true },
  ...
]
```

## Disabling Raw Data Storage

If you don't want to save raw data (not recommended), use:

```bash
python src/fetch_profiles_rapidapi.py \
  --input input_profiles.csv \
  --output results.csv \
  --no-save-raw-data
```

## Reprocessing from Saved Raw Data

### Why Reprocess?

You might want to reprocess when:
- You update target companies in `config/target_companies.txt`
- You add new target schools in `config/target_schools.txt`
- You fix a bug in data extraction logic
- You want to add new calculated fields
- You want to experiment with different extraction rules

### Method 1: Reprocess from Directory

Process all individual `profile_*.json` files:

```bash
python src/reprocess_from_raw.py \
  --raw-data output/raw_data \
  --output reprocessed_results.csv
```

### Method 2: Reprocess from Combined File

Process the single `all_profiles_raw.json` file:

```bash
python src/reprocess_from_raw.py \
  --raw-data output/raw_data/all_profiles_raw.json \
  --output reprocessed_results.csv \
  --combined-file
```

### Example Workflow

1. **Initial scrape** (uses API credits):
   ```bash
   python src/fetch_profiles_rapidapi.py \
     --input input_profiles.csv \
     --output results_v1.csv
   ```
   → Saves raw data to `output/raw_data/`

2. **Update target companies** in `config/target_companies.txt`:
   ```
   monmarché.fr
   Prosol
   Grand Frais
   Naturalia  # NEW company added
   ```

3. **Reprocess** (NO API calls, uses saved data):
   ```bash
   python src/reprocess_from_raw.py \
     --raw-data output/raw_data \
     --output results_v2.csv
   ```
   → New CSV with updated calculations, no API cost!

## Advanced Usage

### Custom Configuration Directory

```bash
python src/reprocess_from_raw.py \
  --raw-data output/raw_data \
  --output results.csv \
  --config-dir my_custom_config
```

### Custom Output Directory

```bash
python src/reprocess_from_raw.py \
  --raw-data output/raw_data \
  --output results.csv \
  --output-dir my_output
```

## Troubleshooting

### "No profile_*.json files found"
- Check that you ran `fetch_profiles_rapidapi.py` first
- Verify the path to `--raw-data` is correct
- Make sure raw data saving wasn't disabled with `--no-save-raw-data`

### "Expected list of profiles, got dict"
- You're using `--combined-file` with a directory path (or vice versa)
- Use `--combined-file` ONLY with `all_profiles_raw.json`
- Use directory path WITHOUT `--combined-file` for `profile_*.json` files

### "Profile data not loading correctly"
- Check the JSON files aren't corrupted
- Verify the file structure matches expected format
- Check logs in `reprocessing.log` for detailed error messages

## Best Practices

1. **Always save raw data** (default behavior) - storage is cheap, API credits are not
2. **Keep backups** of your `output/raw_data/` directory
3. **Use version control** for config files to track changes
4. **Test reprocessing** on a small subset before processing all profiles
5. **Document changes** when you reprocess with different configurations

## File Size Estimates

- Each profile's raw JSON: ~10-50 KB (depending on profile completeness)
- 88 profiles: ~1-5 MB total
- 500 profiles: ~5-25 MB total

This is negligible compared to the cost of re-fetching via API!

## Cost Savings Example

**Scenario**: You have 88 profiles on the Pro plan ($10/month, 500 requests)

- **Without raw data storage**:
  - First run: 88 API calls
  - Fix extraction bug: 88 more API calls
  - Add new target company: 88 more API calls
  - **Total**: 264 API calls

- **With raw data storage**:
  - First run: 88 API calls
  - Fix extraction bug: 0 API calls (reprocess from raw)
  - Add new target company: 0 API calls (reprocess from raw)
  - **Total**: 88 API calls
  - **Savings**: 176 API calls = ~$3.50 saved

## Summary

✅ **Raw data is automatically saved** to `output/raw_data/`
✅ **Reprocess anytime** with `reprocess_from_raw.py`
✅ **No extra API calls** when reprocessing
✅ **Experiment freely** with configurations
✅ **Save money** on API credits
