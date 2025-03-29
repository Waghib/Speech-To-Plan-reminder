"""
Diagnostic script to identify issues with the Speech-To-Plan Reminder application.
"""

import sys
import logging
import importlib
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_import(module_name):
    """Test importing a module and log any errors."""
    logger.info(f"Testing import of {module_name}")
    try:
        module = importlib.import_module(module_name)
        logger.info(f"Successfully imported {module_name}")
        return True, module
    except Exception as e:
        logger.error(f"Error importing {module_name}: {str(e)}")
        logger.error(traceback.format_exc())
        return False, None

def test_database_connection():
    """Test database connection."""
    logger.info("Testing database connection")
    try:
        from app.models.todo import engine
        
        # Test connection
        with engine.connect() as conn:
            logger.info("Successfully connected to database")
            return True
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def run_diagnostics():
    """Run all diagnostic tests."""
    logger.info("Starting diagnostics")
    
    # Test importing key modules
    modules_to_test = [
        "app",
        "app.config",
        "app.models.todo",
        "app.routes.todo_routes",
        "app.routes.transcription_routes",
        "app.services.todo_service",
        "app.services.audio_service",
        "app.services.ai_service"
    ]
    
    import_results = {}
    for module in modules_to_test:
        success, _ = test_import(module)
        import_results[module] = success
    
    # Test database connection
    db_success = test_database_connection()
    
    # Print summary
    logger.info("Diagnostic Summary:")
    logger.info("Import Tests:")
    for module, success in import_results.items():
        logger.info(f"  {module}: {'SUCCESS' if success else 'FAILED'}")
    
    logger.info(f"Database Connection: {'SUCCESS' if db_success else 'FAILED'}")
    
    # Overall assessment
    if all(import_results.values()) and db_success:
        logger.info("All tests passed. The application should be able to start correctly.")
    else:
        logger.info("Some tests failed. Please check the logs for details.")

if __name__ == "__main__":
    run_diagnostics()
