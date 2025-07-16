import asyncio
import concurrent.futures
import cv2
import logging
import numpy as np
import time
from PIL import Image

from services.feature_matching import FeatureMatchingService


class VisionPipelineService:
    """Service for running the computer vision pipeline."""
    
    def __init__(self, model_manager, settings):
        self.model_manager = model_manager
        self.settings = settings
        self.feature_matching = FeatureMatchingService(model_manager, settings)
    
    def run_vision_pipeline(self, image_path: str, original_filename: str):
        """Run the complete vision pipeline on an image."""

        pipeline_start_time = time.time()
        logging.info("PIPELINE START: %s", original_filename)
        
        # Load image
        source_image_bgr = cv2.imread(image_path)
        if source_image_bgr is None:
            logging.error("Could not load image: %s", image_path)
            return []
        
        # YOLO detection
        yolo_start_time = time.time()
        results = self.model_manager.yolo_model(source_image_bgr, verbose=False)
        yolo_end_time = time.time()
        
        detected_boxes = results[0].boxes.xyxy
        logging.info("PERF: YOLO detection found %d cards in %.4f seconds.", 
                    len(detected_boxes), yolo_end_time - yolo_start_time)
        
        # Process each detected card
        analysis_reports = []
        if detected_boxes is not None and len(detected_boxes) > 0:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_to_crop = {
                    executor.submit(self._process_single_crop, source_image_bgr, box, i + 1): box 
                    for i, box in enumerate(detected_boxes)
                }
                
                for future in concurrent.futures.as_completed(future_to_crop):
                    try:
                        if data := future.result():
                            analysis_reports.append(data)
                    except Exception as exc:
                        logging.error("A crop analysis generated an exception: %s", exc, exc_info=True)
        
        logging.info("PIPELINE END: %s. Total time: %.4f seconds.", 
                    original_filename, time.time() - pipeline_start_time)
        return analysis_reports
    
    def _process_single_crop(self, source_image_bgr: np.ndarray, box, crop_idx: int):
        """Process a single detected card crop."""

        crop_start_time = time.time()
        
        # Extract crop coordinates
        x1, y1, x2, y2 = [int(coord) for coord in box]
        crop_bgr = source_image_bgr[y1:y2, x1:x2]
        
        if crop_bgr.size == 0:
            return None
        
        analysis_data = {}
        
        # Hash-based matching
        if any(self.settings.algo_enabled.get(h) for h in ['phash', 'dhash', 'whash']):
            hash_start_time = time.time()
            
            crop_pil = Image.fromarray(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB))
            query_hashes = self.feature_matching.compute_hash_features(crop_pil)
            analysis_data['hash_results'] = self.feature_matching.find_best_hash_match(query_hashes)
            
            logging.info("PERF: Crop #%d hashing took %.4f seconds.", 
                        crop_idx, time.time() - hash_start_time)
        
        # Feature-based matching
        if self.settings.algo_enabled.get('sift') or self.settings.algo_enabled.get('akaze'):
            crop_gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            
            for feature_type in ['SIFT', 'AKAZE']:
                if self.settings.algo_enabled.get(feature_type.lower()):
                    compute_start = time.time()
                    
                    descriptors = self.feature_matching.compute_feature_descriptors(crop_gray, feature_type)
                    logging.info("PERF: Crop #%d %s compute took %.4fs.", 
                                crop_idx, feature_type, time.time() - compute_start)
                    
                    if descriptors is not None:
                        match_start = time.time()
                        result = self.feature_matching.find_best_feature_match(descriptors, feature_type)
                        
                        matcher_name = "FLANN" if self.settings.flann_enabled else "BF"
                        logging.info("PERF: Crop #%d %s %s Match took %.4fs.", 
                                    crop_idx, feature_type, matcher_name, time.time() - match_start)
                        
                        if card_id := result.get('card_id'):
                            card_info = self.model_manager.get_card_info(card_id)
                            card_name = card_info.get('card_name', 'Unknown')
                            logging.info("MATCH_RESULT: Crop #%d %s (%s) -> %s (Score: %d)", 
                                        crop_idx, feature_type, matcher_name, card_name, result['matches'])
                        
                        analysis_data[f'{feature_type.lower()}_result'] = result
        
        logging.info("PERF: Total processing for Crop #%d took %.4f seconds.", 
                    crop_idx, time.time() - crop_start_time)
        return analysis_data