"""CSV export functionality for LinkedIn profile data."""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class CSVExporter:
    """Exports LinkedIn profile data to CSV format."""

    # Column headers in the desired order
    COLUMN_HEADERS = [
        "name",
        "job_titles_at_target_companies",
        "total_years_experience",
        "years_at_target_companies",
        "current_company",
        "linkedin_url",
        "schools_attended",
        "target_school",
        "spoken_languages",
        "english_flag",
        "city_location",
        "paris_flag",
        "years_at_food_retailers"
    ]

    def __init__(self, output_dir: str = "output"):
        """
        Initialize the CSV exporter.

        Args:
            output_dir: Directory to save CSV files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_value(self, value: Any) -> str:
        """
        Sanitize a value for CSV output.

        Args:
            value: Value to sanitize

        Returns:
            Sanitized string value
        """
        if value is None:
            return ""

        # Convert to string
        str_value = str(value).strip()

        # Handle empty strings
        if not str_value:
            return ""

        return str_value

    def export_to_csv(
        self,
        profiles: List[Dict[str, Any]],
        output_file: Optional[str] = None,
        timestamp: bool = True
    ) -> str:
        """
        Export profile data to CSV file.

        Args:
            profiles: List of profile data dictionaries
            output_file: Output file path (if None, generates timestamped filename)
            timestamp: Whether to add timestamp to filename

        Returns:
            Path to the created CSV file
        """
        # Generate filename if not provided
        if not output_file:
            if timestamp:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"profiles_{ts}.csv"
            else:
                output_file = "profiles.csv"

        output_path = self.output_dir / output_file

        try:
            # Create DataFrame with proper column order
            df = pd.DataFrame(profiles)

            # Ensure all expected columns exist
            for col in self.COLUMN_HEADERS:
                if col not in df.columns:
                    df[col] = ""

            # Select columns in the correct order
            df = df[self.COLUMN_HEADERS]

            # Export to CSV with proper escaping
            df.to_csv(
                output_path,
                index=False,
                encoding='utf-8',
                quoting=csv.QUOTE_MINIMAL,
                escapechar='\\'
            )

            logger.info(f"Successfully exported {len(profiles)} profiles to {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            raise

    def export_to_csv_text(self, profiles: List[Dict[str, Any]]) -> str:
        """
        Export profile data to CSV-formatted text block.

        Args:
            profiles: List of profile data dictionaries

        Returns:
            CSV-formatted string
        """
        try:
            # Create DataFrame
            df = pd.DataFrame(profiles)

            # Ensure all expected columns exist
            for col in self.COLUMN_HEADERS:
                if col not in df.columns:
                    df[col] = ""

            # Select columns in the correct order
            df = df[self.COLUMN_HEADERS]

            # Convert to CSV string
            csv_text = df.to_csv(
                index=False,
                encoding='utf-8',
                quoting=csv.QUOTE_MINIMAL
            )

            return csv_text

        except Exception as e:
            logger.error(f"Error creating CSV text: {e}")
            raise

    def append_to_csv(
        self,
        profile: Dict[str, Any],
        output_file: str
    ):
        """
        Append a single profile to an existing CSV file.

        Useful for incremental saves during scraping.

        Args:
            profile: Profile data dictionary
            output_file: Path to CSV file
        """
        output_path = self.output_dir / output_file

        try:
            # Check if file exists
            file_exists = output_path.exists()

            # Open file in append mode
            with open(output_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=self.COLUMN_HEADERS,
                    quoting=csv.QUOTE_MINIMAL,
                    extrasaction='ignore'
                )

                # Write header if file is new
                if not file_exists:
                    writer.writeheader()

                # Write profile data
                writer.writerow(profile)

            logger.debug(f"Appended profile to {output_path}")

        except Exception as e:
            logger.error(f"Error appending to CSV: {e}")
            raise

    def read_csv(self, csv_file: str) -> List[Dict[str, Any]]:
        """
        Read profiles from an existing CSV file.

        Useful for resuming interrupted scraping sessions.

        Args:
            csv_file: Path to CSV file

        Returns:
            List of profile dictionaries
        """
        csv_path = self.output_dir / csv_file

        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            profiles = df.to_dict('records')
            logger.info(f"Read {len(profiles)} profiles from {csv_path}")
            return profiles

        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            raise

    def get_processed_urls(self, csv_file: str) -> set:
        """
        Get set of profile URLs that have already been processed.

        Useful for resuming scraping and avoiding duplicates.

        Args:
            csv_file: Path to CSV file

        Returns:
            Set of LinkedIn profile URLs
        """
        csv_path = self.output_dir / csv_file

        if not csv_path.exists():
            return set()

        try:
            profiles = self.read_csv(csv_file)
            urls = {p.get('linkedin_url', '') for p in profiles if p.get('linkedin_url')}
            logger.info(f"Found {len(urls)} already processed URLs")
            return urls

        except Exception as e:
            logger.warning(f"Error getting processed URLs: {e}")
            return set()


def export_profiles(
    profiles: List[Dict[str, Any]],
    output_file: Optional[str] = None,
    output_dir: str = "output"
) -> str:
    """
    Convenience function to export profiles to CSV.

    Args:
        profiles: List of profile data dictionaries
        output_file: Output file name
        output_dir: Output directory

    Returns:
        Path to created CSV file
    """
    exporter = CSVExporter(output_dir=output_dir)
    return exporter.export_to_csv(profiles, output_file=output_file)


def export_profiles_text(profiles: List[Dict[str, Any]]) -> str:
    """
    Convenience function to export profiles as CSV text.

    Args:
        profiles: List of profile data dictionaries

    Returns:
        CSV-formatted string
    """
    exporter = CSVExporter()
    return exporter.export_to_csv_text(profiles)


if __name__ == "__main__":
    # Example usage with mock data
    import sys

    logging.basicConfig(level=logging.INFO)

    # Create some mock profile data
    mock_profiles = [
        {
            "name": "John Doe",
            "job_titles_at_target_companies": "Manager, Director",
            "total_years_experience": 10.5,
            "years_at_target_companies": 3.0,
            "current_company": "Grand Frais",
            "linkedin_url": "https://www.linkedin.com/in/johndoe",
            "schools_attended": "HEC Paris, University of Paris",
            "target_school": "HEC Paris",
            "spoken_languages": "French, English",
            "english_flag": "english",
            "city_location": "Paris, Île-de-France",
            "paris_flag": "Paris et périphérie",
            "years_at_food_retailers": 5.5
        },
        {
            "name": "Jane Smith",
            "job_titles_at_target_companies": "",
            "total_years_experience": 8.0,
            "years_at_target_companies": 0.0,
            "current_company": "Tech Company",
            "linkedin_url": "https://www.linkedin.com/in/janesmith",
            "schools_attended": "ESCP Business School",
            "target_school": "ESCP Business School",
            "spoken_languages": "French, Spanish",
            "english_flag": "",
            "city_location": "Lyon, France",
            "paris_flag": "",
            "years_at_food_retailers": 0.0
        }
    ]

    exporter = CSVExporter()

    # Export to file
    output_path = exporter.export_to_csv(mock_profiles, output_file="test_profiles.csv")
    print(f"Exported to: {output_path}")

    # Export as text
    csv_text = exporter.export_to_csv_text(mock_profiles)
    print("\nCSV Text Output:")
    print(csv_text)
