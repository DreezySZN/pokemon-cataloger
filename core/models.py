import cv2
import json
import logging
import numpy as np
import os
import pandas as pd
import time
import torch
from ultralytics import YOLO
from typing import Dict, Optional


class ModelManager:
    """Manages YOLO model and feature detection components."""
    
    def __init__(self, settings):
        self.settings = settings
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logging.info("--- Using device: %s ---", self.device)
        
        # Load YOLO model
        self.yolo_model = YOLO(settings.model_path)
        self.yolo_model.to(self.device)
        
        # Load card information
        self.card_info_df = pd.read_csv(settings.csv_path)
        self.card_info_df['card_id_str'] = self.card_info_df['image_filename'].str.replace('.jpg', '', regex=False)
        self.card_lookup = self.card_info_df.set_index('card_id_str')[['card_name', 'rarity', 'image_filename', 'card_id']].to_dict(orient='index')
        
        # Load hash database
        with open(settings.hash_db_path, 'r') as f:
            self.hash_database = json.load(f)
        
        # Initialize feature detectors
        self.sift = cv2.SIFT_create() if settings.algo_enabled.get('sift') else None
        self.akaze = cv2.AKAZE_create() if settings.algo_enabled.get('akaze') else None
        
        # Initialize matchers
        self.bf_matcher = cv2.BFMatcher()
        self._setup_flann_matchers()
        
        # Initialize CLAHE for image enhancement
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        
        # Load feature databases
        self.sift_features_db = self._load_features_to_memory(settings.sift_features_dir, 'SIFT') if settings.algo_enabled.get('sift') else {}
        self.akaze_features_db = self._load_features_to_memory(settings.akaze_features_dir, 'AKAZE') if settings.algo_enabled.get('akaze') else {}
        
        logging.info("--- Models and data loaded successfully. ---")
        logging.info("--- Feature matching mode: %s ---", "FLANN" if settings.flann_enabled else "Brute-Force (BF)")
    
    def _setup_flann_matchers(self):
        """Initialize FLANN matchers for different feature types."""

        # SIFT FLANN matcher
        flann_index_kdtree = 1
        index_params_sift = dict(algorithm=flann_index_kdtree, trees=5)
        search_params = dict(checks=50)
        self.flann_matcher_sift = cv2.FlannBasedMatcher(index_params_sift, search_params)
        
        # AKAZE FLANN matcher
        flann_index_lsh = 6
        index_params_akaze = dict(algorithm=flann_index_lsh, table_number=6, key_size=12, multi_probe_level=1)
        self.flann_matcher_akaze = cv2.FlannBasedMatcher(index_params_akaze, search_params)
    
    def _load_features_to_memory(self, features_dir: str, feature_type: str) -> Dict[str, np.ndarray]:
        """Load pre-computed features from disk to memory."""

        start_time = time.time()
        logging.info("Pre-loading %s features from %s...", feature_type, features_dir)
        
        db = {}
        if not os.path.isdir(features_dir):
            return db
        
        for filename in os.listdir(features_dir):
            if filename.endswith('.npy'):
                card_id = os.path.splitext(filename)[0]
                ref_path = os.path.join(features_dir, filename)
                
                try:
                    descriptors = np.load(ref_path)
                    if descriptors.size > 0:
                        if feature_type == 'SIFT' and descriptors.dtype != np.float32:
                            descriptors = descriptors.astype(np.float32)
                        db[card_id] = descriptors
                except Exception as e:
                    logging.warning("Could not load feature file %s: %s", filename, e)
        
        logging.info("Loaded %d %s feature sets in %.2f seconds.", len(db), feature_type, time.time() - start_time)
        return db
    
    def get_matcher(self, feature_type: str, use_flann: bool = False):
        """Get appropriate matcher for feature type."""

        if use_flann:
            if feature_type == 'SIFT':
                return self.flann_matcher_sift, "FLANN"
            elif feature_type == 'AKAZE':
                return self.flann_matcher_akaze, "FLANN"
        
        return self.bf_matcher, "BF"
    
    def get_feature_database(self, feature_type: str) -> Dict[str, np.ndarray]:
        """Get feature database for specified type."""

        if feature_type == 'SIFT':
            return self.sift_features_db
        elif feature_type == 'AKAZE':
            return self.akaze_features_db
        return {}
    
    def get_card_info(self, card_id: str) -> Dict:
        """Get card information by ID."""
        
        return self.card_lookup.get(card_id, {})
