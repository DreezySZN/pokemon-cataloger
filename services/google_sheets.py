import logging
import os
import pandas as pd
import threading
import time
import gspread
from google.oauth2.service_account import Credentials

class GoogleSheetsService:
    """Service for Google Sheets integration."""
    
    REQUIRED_COLS = ['timestamp', 'deviceAccount', 'devicePassword', 'card_name', 'rarity', 'card_id']
    
    def __init__(self, settings):
        self.settings = settings
        self.enabled = settings.gsheets_enabled
        
        if not settings.gsheets_enabled:
            logging.warning("Google Sheets integration requested but gspread not available")
    
    def authorize_gspread(self):
        """Authorize Google Sheets access."""
        
        try:
            creds = Credentials.from_service_account_file(
                self.settings.gsheets_cred_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            )
            return gspread.authorize(creds)
        except Exception as e:
            logging.error("G-SHEETS: Authorization failed: %s", e)
            return None
    
    def sync_to_google_sheets(self):
        """Sync CSV data to Google Sheets."""
        
        if not self.enabled or not os.path.exists(self.settings.csv_log_path):
            return
        
        try:
            if os.path.getsize(self.settings.csv_log_path) == 0:
                logging.info("G-SHEETS: CSV log is empty. Nothing to sync.")
                return
            
            df = pd.read_csv(self.settings.csv_log_path)
            
            # Validate required columns
            missing_cols = [col for col in self.REQUIRED_COLS if col not in df.columns]
            if missing_cols:
                logging.error(
                    "G-SHEETS: Sync failed. Missing required columns: %s. "
                    "Delete the CSV file to regenerate it.",
                    ', '.join(missing_cols)
                )
                return
            
            # Handle upload status column
            if 'uploaded_to_sheets' not in df.columns:
                df['uploaded_to_sheets'] = False
            
            df['uploaded_to_sheets'] = df['uploaded_to_sheets'].fillna(False).astype(bool)
            
            # Get unsynced rows
            unsynced_df = df[df['uploaded_to_sheets'] == False].copy()
            if unsynced_df.empty:
                return  # Nothing new to sync
            
            unsynced_df.fillna('', inplace=True)
            logging.info("G-SHEETS: Found %d new rows to sync.", len(unsynced_df))
            
            # Authorize and get spreadsheet
            gc = self.authorize_gspread()
            if not gc:
                return
            
            try:
                spreadsheet = gc.open(self.settings.gsheets_spreadsheet_name)
            except gspread.SpreadsheetNotFound:
                spreadsheet = gc.create(self.settings.gsheets_spreadsheet_name)
                spreadsheet.share(gc.auth.service_account_email, perm_type='user', role='writer')
            
            try:
                worksheet = spreadsheet.worksheet("Raw Data")
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(title="Raw Data", rows="1000", cols="20")
                worksheet.append_row(self.REQUIRED_COLS)
            
            # Upload new rows
            rows_to_append = unsynced_df[self.REQUIRED_COLS].values.tolist()
            worksheet.append_rows(rows_to_append, value_input_option='USER_ENTERED')
            
            # Mark as uploaded
            df.loc[unsynced_df.index, 'uploaded_to_sheets'] = True
            df.to_csv(self.settings.csv_log_path, index=False)
            
            logging.info("G-SHEETS: Successfully synced %d new rows.", len(rows_to_append))
            
        except pd.errors.EmptyDataError:
            logging.info("G-SHEETS: CSV log file is empty. Nothing to sync.")
        except Exception as e:
            logging.error("G-SHEETS: An error occurred during sync: %s", e, exc_info=True)
    
    def start_sync_thread(self):
        """Start background sync thread."""

        if not self.enabled:
            return
        
        def sync_loop():
            logging.info("G-SHEETS: Background sync thread started.")
            while True:
                try:
                    self.sync_to_google_sheets()
                except Exception as e:
                    logging.error("G-SHEETS: Unhandled exception in sync thread: %s", e, exc_info=True)
                time.sleep(self.settings.gsheets_sync_interval)
        
        thread = threading.Thread(target=sync_loop, daemon=True)
        thread.start()