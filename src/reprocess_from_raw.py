"""Reprocess LinkedIn profiles from saved raw API data.

This script allows you to re-extract data from previously saved raw API responses
without making new API calls. Useful when you want to:
- Change extraction logic (e.g., modify target companies/schools)
- Add new calculated fields
- Fix bugs in data extraction
- Experiment with different configurations

All without wasting API credits!
"""

import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from data_calculator import ProfileDataCalculator
from csv_exporter import CSVExporter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('reprocessing.log')
    ]
)

logger = logging.getLogger(__name__)


def load_raw_data_from_directory(raw_data_dir: str) -> List[Dict[str, Any]]:
    """
    Load all raw profile data from individual JSON files in a directory.

    Args:
        raw_data_dir: Directory containing profile_*.json files

    Returns:
        List of profile data dictionaries
    """
    raw_data_path = Path(raw_data_dir)

    if not raw_data_path.exists():
        raise FileNotFoundError(f"Raw data directory not found: {raw_data_dir}")

    # Find all profile JSON files
    profile_files = sorted(raw_data_path.glob("profile_*.json"))

    if not profile_files:
        raise ValueError(f"No profile_*.json files found in {raw_data_dir}")

    logger.info(f"Found {len(profile_files)} raw profile files")

    profiles = []
    for profile_file in profile_files:
        try:
            with open(profile_file, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
                profiles.append(profile_data)
        except Exception as e:
            logger.error(f"Error loading {profile_file}: {e}")

    return profiles


def load_raw_data_from_combined_file(combined_file: str) -> List[Dict[str, Any]]:
    """
    Load all raw profile data from a combined JSON file.

    Args:
        combined_file: Path to all_profiles_raw.json

    Returns:
        List of profile data dictionaries
    """
    combined_path = Path(combined_file)

    if not combined_path.exists():
        raise FileNotFoundError(f"Combined raw data file not found: {combined_file}")

    with open(combined_path, 'r', encoding='utf-8') as f:
        profiles = json.load(f)

    if not isinstance(profiles, list):
        raise ValueError(f"Expected list of profiles, got {type(profiles)}")

    logger.info(f"Loaded {len(profiles)} profiles from combined file")

    return profiles


def reprocess_profiles(
    raw_data_source: str,
    output_csv: str,
    config_dir: str = "config",
    output_dir: str = "output",
    use_combined_file: bool = False
):
    """
    Reprocess profiles from saved raw data.

    Args:
        raw_data_source: Path to raw data directory or combined JSON file
        output_csv: Output CSV filename
        config_dir: Configuration directory
        output_dir: Output directory
        use_combined_file: If True, treat raw_data_source as a single JSON file
    """
    logger.info("=" * 80)
    logger.info("LinkedIn Profile Reprocessor - Starting")
    logger.info("=" * 80)

    # Load raw data
    logger.info(f"\nLoading raw profile data from {raw_data_source}...")

    try:
        if use_combined_file:
            profiles = load_raw_data_from_combined_file(raw_data_source)
        else:
            profiles = load_raw_data_from_directory(raw_data_source)
    except Exception as e:
        logger.error(f"Error loading raw data: {e}")
        return

    if not profiles:
        logger.error("No profile data loaded!")
        return

    logger.info(f"Successfully loaded {len(profiles)} profiles\n")

    # Initialize components
    data_calculator = ProfileDataCalculator(config_dir=config_dir)
    csv_exporter = CSVExporter(output_dir=output_dir)

    # Process profiles
    processed_profiles = []
    failed_count = 0

    for i, profile_data in enumerate(profiles, 1):
        logger.info(f"[{i}/{len(profiles)}] Reprocessing profile...")

        # Check if profile fetch was successful
        if not profile_data.get("success"):
            logger.warning(f"✗ Skipping failed profile: {profile_data.get('error', 'Unknown error')}")
            failed_count += 1
            continue

        try:
            # Extract and calculate fields
            extracted_data = data_calculator.extract_profile_fields(profile_data)
            processed_profiles.append(extracted_data)

            logger.info(f"✓ Successfully processed: {extracted_data.get('name', 'Unknown')}")
            logger.info(f"  Current company: {extracted_data.get('current_company', 'N/A')}")
            logger.info(f"  Total experience: {extracted_data.get('total_years_experience', 0)} years\n")

        except Exception as e:
            logger.error(f"✗ Error extracting data: {e}", exc_info=True)
            failed_count += 1

    # Export results
    logger.info(f"\n[FINAL STEP] Exporting results...\n")

    if processed_profiles:
        output_path = csv_exporter.export_to_csv(
            processed_profiles,
            output_file=output_csv,
            timestamp=False
        )

        csv_text = csv_exporter.export_to_csv_text(processed_profiles)

        logger.info("=" * 80)
        logger.info("REPROCESSING COMPLETE!")
        logger.info("=" * 80)
        logger.info(f"Total profiles processed: {len(processed_profiles)}/{len(profiles)}")
        logger.info(f"Failed/skipped: {failed_count}")
        logger.info(f"Success rate: {len(processed_profiles)/len(profiles)*100:.1f}%")
        logger.info(f"Output file: {output_path}")
        logger.info(f"\nCSV Output:\n")
        print(csv_text)

    else:
        logger.warning("No profiles were successfully processed")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Reprocess LinkedIn profiles from saved raw API data'
    )

    parser.add_argument(
        '--raw-data',
        required=True,
        help='Path to raw data directory or combined JSON file'
    )

    parser.add_argument(
        '--output',
        default='reprocessed_profiles.csv',
        help='Output CSV filename (default: reprocessed_profiles.csv)'
    )

    parser.add_argument(
        '--config-dir',
        default='config',
        help='Configuration directory (default: config)'
    )

    parser.add_argument(
        '--output-dir',
        default='output',
        help='Output directory (default: output)'
    )

    parser.add_argument(
        '--combined-file',
        action='store_true',
        help='Treat raw-data as a single JSON file (all_profiles_raw.json) instead of a directory'
    )

    args = parser.parse_args()

    # Reprocess profiles
    try:
        reprocess_profiles(
            raw_data_source=args.raw_data,
            output_csv=args.output,
            config_dir=args.config_dir,
            output_dir=args.output_dir,
            use_combined_file=args.combined_file
        )
    except KeyboardInterrupt:
        logger.info("\nReprocessing interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
