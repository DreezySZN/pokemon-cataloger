import csv
import logging
import os
from datetime import datetime
from typing import Dict


class LoggingService:
    """Service for handling CSV logging."""
    
    CSV_HEADERS = ['timestamp', 'deviceAccount', 'devicePassword', 'card_name', 'rarity', 'card_id', 'uploaded_to_sheets']
    
    def __init__(self, settings):
        self.settings = settings
        self.enabled = settings.csv_log_enabled
        self.log_path = settings.csv_log_path
    
    def log_detection(self, log_data: Dict):
        """Log a card detection to CSV."""
        if not self.enabled:
            return
        
        log_data['uploaded_to_sheets'] = False
        
        try:
            log_dir = os.path.dirname(self.log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            
            file_exists = os.path.isfile(self.log_path)
            
            with open(self.log_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow(log_data)
                
        except (IOError, OSError) as e:
            logging.error("Could not write to CSV log file at %s: %s", self.log_path, e)