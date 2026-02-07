"""Data extraction and calculation logic for LinkedIn profiles."""

import json
import logging
import re
from datetime import datetime
from dateutil import parser as date_parser
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from fuzzywuzzy import fuzz, process

logger = logging.getLogger(__name__)


class ProfileDataCalculator:
    """Extracts and calculates structured data from LinkedIn profiles."""

    def __init__(self, config_dir: str = "config"):
        """
        Initialize the data calculator.

        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = Path(config_dir)
        self.target_schools = self._load_config("target_schools.txt")
        self.target_companies = self._load_config("target_companies.txt")
        self.food_retailers = self._load_config("food_retailers.txt")

    def _load_config(self, filename: str) -> List[str]:
        """Load configuration file as list of strings."""
        config_path = self.config_dir / filename
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.warning(f"Could not load {filename}: {e}")
            return []

    def _parse_profile_data(self, raw_data: Any) -> Dict[str, Any]:
        """
        Parse the raw profile data from MCP server.

        The MCP server might return data in various formats (JSON string, dict, etc.)
        This method normalizes it into a consistent structure.
        """
        if not raw_data:
            return {}

        # If it's a string, try to parse as JSON
        if isinstance(raw_data, str):
            try:
                return json.loads(raw_data)
            except json.JSONDecodeError:
                logger.warning("Could not parse raw_data as JSON")
                return {"raw_text": raw_data}

        # If it's already a dict, return it
        if isinstance(raw_data, dict):
            return raw_data

        # Otherwise, convert to string
        return {"raw_text": str(raw_data)}

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse a date string into a datetime object.

        Handles various LinkedIn date formats like "Jan 2020", "2020", "Present", etc.
        """
        if not date_str or not isinstance(date_str, str):
            return None

        date_str = date_str.strip().lower()

        # Handle "Present" or "Current"
        if date_str in ["present", "current", "now"]:
            return datetime.now()

        try:
            # Try standard parsing first
            return date_parser.parse(date_str, fuzzy=True)
        except Exception:
            # Try manual parsing for formats like "2020" or "Jan 2020"
            try:
                # Just year
                if re.match(r'^\d{4}$', date_str):
                    return datetime(int(date_str), 1, 1)

                # Month and year (various formats)
                month_match = re.search(r'(\w+)\s+(\d{4})', date_str)
                if month_match:
                    return date_parser.parse(f"{month_match.group(1)} {month_match.group(2)}")

            except Exception:
                pass

        logger.warning(f"Could not parse date: {date_str}")
        return None

    def _calculate_duration(self, start_date: str, end_date: str) -> float:
        """
        Calculate duration between two dates in years, rounded to nearest 0.5.

        Args:
            start_date: Start date string
            end_date: End date string (can be "Present")

        Returns:
            Duration in years (rounded to nearest 0.5)
        """
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)

        if not start:
            return 0.0

        if not end:
            end = datetime.now()

        # Calculate duration in months
        months = (end.year - start.year) * 12 + (end.month - start.month)

        # Convert to years
        years = months / 12.0

        # Round to nearest 0.5
        return round(years * 2) / 2

    def _fuzzy_match_school(self, school_name: str) -> Optional[str]:
        """
        Fuzzy match a school name against target schools.

        Args:
            school_name: School name from profile

        Returns:
            Matched target school name, or None if no match above threshold
        """
        if not school_name:
            return None

        # Use fuzzywuzzy to find best match
        result = process.extractOne(
            school_name,
            self.target_schools,
            scorer=fuzz.token_sort_ratio
        )

        if result:
            match_name, score = result[0], result[1]
            logger.debug(f"School match: '{school_name}' -> '{match_name}' (score: {score})")

            # Return match if score is above threshold (85%)
            if score >= 85:
                return match_name

        return None

    def _is_target_company(self, company_name: str) -> bool:
        """Check if company is in target companies list."""
        if not company_name:
            return False

        company_lower = company_name.lower().strip()
        return any(target.lower() in company_lower or company_lower in target.lower()
                   for target in self.target_companies)

    def _is_food_retailer(self, company_name: str) -> bool:
        """Check if company is in food retailers list."""
        if not company_name:
            return False

        company_lower = company_name.lower().strip()
        return any(retailer.lower() in company_lower or company_lower in retailer.lower()
                   for retailer in self.food_retailers)

    def _extract_experience_data(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract experience entries from profile.

        Returns:
            List of experience dictionaries
        """
        # The profile structure depends on what the MCP server returns
        # Common keys: 'experience', 'positions', 'work_history', etc.

        experience_keys = ['experience', 'positions', 'work_history', 'experiences']

        for key in experience_keys:
            if key in profile:
                exp_data = profile[key]
                if isinstance(exp_data, list):
                    return exp_data
                elif isinstance(exp_data, str):
                    # Try to parse as JSON
                    try:
                        parsed = json.loads(exp_data)
                        if isinstance(parsed, list):
                            return parsed
                    except Exception:
                        pass

        return []

    def _extract_education_data(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract education entries from profile.

        Returns:
            List of education dictionaries
        """
        education_keys = ['education', 'schools', 'educations']

        for key in education_keys:
            if key in profile:
                edu_data = profile[key]
                if isinstance(edu_data, list):
                    return edu_data
                elif isinstance(edu_data, str):
                    try:
                        parsed = json.loads(edu_data)
                        if isinstance(parsed, list):
                            return parsed
                    except Exception:
                        pass

        return []

    def extract_profile_fields(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract all 13 required fields from a profile.

        Args:
            profile_data: Profile data dictionary from MCP server

        Returns:
            Dictionary with all extracted fields
        """
        # Parse the raw profile data
        profile = self._parse_profile_data(profile_data.get("raw_data", {}))

        # Get the profile URL
        profile_url = profile_data.get("url", "")

        # Initialize result with empty fields
        result = {
            "name": "",
            "job_titles_at_target_companies": "",
            "total_years_experience": 0.0,
            "years_at_target_companies": 0.0,
            "current_company": "",
            "linkedin_url": profile_url,
            "schools_attended": "",
            "target_school": "",
            "spoken_languages": "",
            "english_flag": "",
            "city_location": "",
            "paris_flag": "",
            "years_at_food_retailers": 0.0
        }

        # Extract name
        name_keys = ['name', 'full_name', 'fullName', 'title']
        for key in name_keys:
            if key in profile and profile[key]:
                result["name"] = str(profile[key]).strip()
                break

        # Extract location
        location_keys = ['location', 'city', 'region', 'locality']
        for key in location_keys:
            if key in profile and profile[key]:
                result["city_location"] = str(profile[key]).strip()
                break

        # Set Paris flag
        if result["city_location"]:
            location_lower = result["city_location"].lower()
            if "paris" in location_lower or "île-de-france" in location_lower or "ile-de-france" in location_lower:
                result["paris_flag"] = "Paris et périphérie"

        # Extract languages
        languages_keys = ['languages', 'language', 'languageSkills']
        for key in languages_keys:
            if key in profile:
                langs = profile[key]
                if isinstance(langs, list):
                    lang_names = [str(lang.get('name', lang)) if isinstance(lang, dict) else str(lang)
                                  for lang in langs]
                    result["spoken_languages"] = ", ".join(lang_names)
                elif isinstance(langs, str):
                    result["spoken_languages"] = langs
                break

        # Set English flag
        if result["spoken_languages"]:
            langs_lower = result["spoken_languages"].lower()
            if "english" in langs_lower or "anglais" in langs_lower:
                result["english_flag"] = "english"

        # Process experience data
        experiences = self._extract_experience_data(profile)

        target_company_titles = []
        total_experience_years = 0.0
        target_company_years = 0.0
        food_retailer_years = 0.0
        current_company = ""
        most_recent_end = None

        for exp in experiences:
            if not isinstance(exp, dict):
                continue

            # Get company name
            company = exp.get('company', exp.get('companyName', exp.get('organization', '')))
            if isinstance(company, dict):
                company = company.get('name', '')
            company = str(company).strip()

            # Get title
            title = exp.get('title', exp.get('position', exp.get('role', '')))
            title = str(title).strip()

            # Get dates
            start = exp.get('start', exp.get('startDate', exp.get('start_date', '')))
            end = exp.get('end', exp.get('endDate', exp.get('end_date', '')))

            # Handle date objects or dicts
            if isinstance(start, dict):
                start = f"{start.get('month', '')} {start.get('year', '')}".strip()
            if isinstance(end, dict):
                end = f"{end.get('month', '')} {end.get('year', '')}".strip()

            start = str(start) if start else ""
            end = str(end) if end else ""

            # Calculate duration for this position
            duration = self._calculate_duration(start, end) if start else 0.0
            total_experience_years += duration

            # Track most recent position
            end_date = self._parse_date(end) if end else datetime.now()
            if end_date and (not most_recent_end or end_date > most_recent_end):
                most_recent_end = end_date
                current_company = company

            # Check if target company
            if self._is_target_company(company):
                if title:
                    target_company_titles.append(title)
                target_company_years += duration

            # Check if food retailer
            if self._is_food_retailer(company):
                food_retailer_years += duration

        result["job_titles_at_target_companies"] = ", ".join(target_company_titles)
        result["total_years_experience"] = total_experience_years
        result["years_at_target_companies"] = target_company_years
        result["current_company"] = current_company
        result["years_at_food_retailers"] = food_retailer_years

        # Process education data
        educations = self._extract_education_data(profile)
        school_names = []
        target_school = None

        for edu in educations:
            if not isinstance(edu, dict):
                continue

            school = edu.get('school', edu.get('schoolName', edu.get('institution', '')))
            if isinstance(school, dict):
                school = school.get('name', '')
            school = str(school).strip()

            if school:
                school_names.append(school)

                # Try fuzzy matching for target schools
                if not target_school:
                    matched = self._fuzzy_match_school(school)
                    if matched:
                        target_school = matched

        result["schools_attended"] = ", ".join(school_names)
        result["target_school"] = target_school if target_school else ""

        return result


def calculate_profile_data(
    profile_data: Dict[str, Any],
    config_dir: str = "config"
) -> Dict[str, Any]:
    """
    Convenience function to calculate profile fields.

    Args:
        profile_data: Profile data from MCP server
        config_dir: Configuration directory path

    Returns:
        Dictionary with extracted fields
    """
    calculator = ProfileDataCalculator(config_dir=config_dir)
    return calculator.extract_profile_fields(profile_data)


if __name__ == "__main__":
    # Example usage with mock data
    import sys
    import json

    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) < 2:
        print("Usage: python data_calculator.py <profile_json_file>")
        sys.exit(1)

    with open(sys.argv[1], 'r') as f:
        profile_data = json.load(f)

    calculator = ProfileDataCalculator()
    result = calculator.extract_profile_fields(profile_data)

    print("\nExtracted Profile Data:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
