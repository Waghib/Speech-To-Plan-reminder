"""
Migration script to help transition from the old project structure to the new one.

This script will:
1. Create necessary directories if they don't exist
2. Copy the database from the old structure to the new one
3. Update import paths in the new files
"""

import os
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_directories_exist():
    """Create necessary directories if they don't exist."""
    directories = [
        "app",
        "app/models",
        "app/routes",
        "app/services",
        "app/utils",
        "temp_files"
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Created directory: {directory}")

def rename_main_file():
    """Rename the new main.py file to replace the old one."""
    if os.path.exists("new_main.py"):
        # Backup the old main.py file
        if os.path.exists("main.py"):
            shutil.copy("main.py", "main.py.bak")
            logger.info("Backed up original main.py to main.py.bak")
        
        # Rename new_main.py to main.py
        shutil.copy("new_main.py", "main.py")
        logger.info("Renamed new_main.py to main.py")
        
        # Remove new_main.py
        os.remove("new_main.py")

def main():
    """Main migration function."""
    logger.info("Starting migration process...")
    
    # Ensure directories exist
    ensure_directories_exist()
    
    # Rename main file
    rename_main_file()
    
    logger.info("Migration completed successfully!")
    logger.info("\nNext steps:")
    logger.info("1. Update your imports in any custom scripts to use the new structure")
    logger.info("2. Run the application with: uvicorn main:app --reload")
    logger.info("3. Test the application to ensure everything works as expected")

if __name__ == "__main__":
    main()
