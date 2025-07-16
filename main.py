import logging
import sys

from config.settings import Settings
from core.bot import CardDetectionBot
from helpers.setup_logging import setup_logs


def main():
    """Main entry point for the application."""
    try:
        settings = Settings()
        
        setup_logs(settings.log_directory)
        
        bot = CardDetectionBot(settings)
        bot.run()
        
    except Exception as e:
        logging.critical("Fatal error during startup: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()