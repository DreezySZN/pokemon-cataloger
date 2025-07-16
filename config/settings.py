import configparser
import os
import logging


class Settings:
    """Centralized configuration management."""
    
    def __init__(self, config_path: str = 'config.ini'):
        self.config = configparser.ConfigParser()
        self.config_path = config_path
        self._load_config()
        self._validate_config()
    
    def _load_config(self):
        """Load configuration from file."""

        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        self.config.read(self.config_path)
    
    def _validate_config(self):
        """Validate required configuration sections and keys."""

        required_sections = {
            'Discord': ['bot_token', 'target_channel_id'],
            'Paths': ['base_path', 'model_path', 'csv_path', 'hash_db_path'],
            'Algorithms': ['phash_enabled', 'dhash_enabled', 'whash_enabled', 'sift_enabled', 'akaze_enabled', 'priority']
        }
        
        for section, keys in required_sections.items():
            if not self.config.has_section(section):
                raise configparser.NoSectionError(f"Missing required section: {section}")
            
            for key in keys:
                if not self.config.has_option(section, key):
                    raise configparser.NoOptionError(f"Missing required option: {key} in section {section}")
    


    # Discord settings
    @property
    def bot_token(self):
        return self.config.get('Discord', 'bot_token')
    
    @property
    def target_channel_id(self):
        return self.config.getint('Discord', 'target_channel_id')
    


    # Path settings
    @property
    def base_path(self):
        return self.config.get('Paths', 'base_path')
    
    @property
    def model_path(self):
        return os.path.join(self.base_path, self.config.get('Paths', 'model_path'))
    
    @property
    def csv_path(self):
        return os.path.join(self.base_path, self.config.get('Paths', 'csv_path'))
    
    @property
    def hash_db_path(self):
        return os.path.join(self.base_path, self.config.get('Paths', 'hash_db_path'))
    
    @property
    def sift_features_dir(self):
        return os.path.join(self.base_path, self.config.get('Paths', 'sift_features_dir'))
    
    @property
    def akaze_features_dir(self):
        return os.path.join(self.base_path, self.config.get('Paths', 'akaze_features_dir'))
    
    @property
    def temp_dir(self):
        return os.path.join(self.base_path, 'data/temp')
    
    @property
    def log_directory(self):
        return self.config.get('Logging', 'log_directory', fallback='logs')
    


    # Algorithm settings
    @property
    def algo_enabled(self):
        return {
            'phash': self.config.getboolean('Algorithms', 'phash_enabled'),
            'dhash': self.config.getboolean('Algorithms', 'dhash_enabled'),
            'whash': self.config.getboolean('Algorithms', 'whash_enabled'),
            'sift': self.config.getboolean('Algorithms', 'sift_enabled'),
            'akaze': self.config.getboolean('Algorithms', 'akaze_enabled'),
        }
    
    @property
    def algo_priority(self):
        return [algo.strip() for algo in self.config.get('Algorithms', 'priority').split(',')]
    
    @property
    def flann_enabled(self):
        return self.config.getboolean('Algorithms', 'flann_enabled', fallback=False)
    


    # CSV logging settings
    @property
    def csv_log_enabled(self):
        return self.config.getboolean('CSVLogging', 'enable_csv_log', fallback=False)
    
    @property
    def csv_log_path(self):
        return self.config.get('CSVLogging', 'csv_log_path')
    


    # Historical processing settings
    @property
    def parse_history(self):
        return self.config.getboolean('Historical', 'parse_history', fallback=False)
    
    @property
    def last_message_id(self):
        return self.config.get('Historical', 'last_message_id', fallback=None)
    


    # Google Sheets settings
    @property
    def gsheets_enabled(self):
        return self.config.getboolean('GoogleSheets', 'enabled', fallback=False)
    
    @property
    def gsheets_cred_path(self):
        return os.path.join(self.base_path, self.config.get('GoogleSheets', 'credentials_path'))
    
    @property
    def gsheets_spreadsheet_name(self):
        return self.config.get('GoogleSheets', 'spreadsheet_name')
    
    @property
    def gsheets_sync_interval(self):
        return self.config.getint('GoogleSheets', 'sync_interval_seconds', fallback=300)
    
    
    # Supabase settings
    @property
    def supabase_enabled(self):
        return self.config.getboolean('Supabase', 'enabled', fallback=False)
    
    @property
    def supabase_url(self):
        return self.config.get('Supabase', 'url', fallback='')
    
    @property
    def supabase_key(self):
        return self.config.get('Supabase', 'service_role_key', fallback='')
    
    @property
    def supabase_table_name(self):
        return self.config.get('Supabase', 'table_name', fallback='accounts')
    


    def update_last_message_id(self, message_id: str):
        """Update the last processed message ID in config."""

        if not message_id:
            return
        
        try:
            self.config.set('Historical', 'last_message_id', str(message_id))
            with open(self.config_path, 'w') as configfile:
                self.config.write(configfile)
        except IOError as e:
            logging.error("Could not write progress to config.ini: %s", e)
    
    def disable_historical_parsing(self):
        """Disable historical parsing after completion."""

        try:
            self.config.set('Historical', 'parse_history', 'false')
            with open(self.config_path, 'w') as configfile:
                self.config.write(configfile)
        except IOError as e:
            logging.error("Could not disable historical parsing in config.ini: %s", e)