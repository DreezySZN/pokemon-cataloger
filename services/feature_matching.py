import cv2
import imagehash
import numpy as np
from PIL import Image
from typing import Dict


class FeatureMatchingService:
    """Service for handling different feature matching algorithms."""
    
    def __init__(self, model_manager, settings):
        self.model_manager = model_manager
        self.settings = settings
    
    def find_best_hash_match(self, query_hashes: Dict[str, str]):
        """Find best match using perceptual hashing algorithms."""

        results = {algo: {'card_id': None, 'distance': float('inf')} for algo in ['phash', 'dhash', 'whash']}
        
        for card_id, ref_hashes in self.model_manager.hash_database.items():
            for algo in results.keys():
                if self.settings.algo_enabled.get(algo) and query_hashes.get(algo):
                    try:
                        query_hash = imagehash.hex_to_hash(query_hashes[algo])
                        ref_hash = imagehash.hex_to_hash(ref_hashes[algo])
                        distance = query_hash - ref_hash
                        
                        if distance < results[algo]['distance']:
                            results[algo]['distance'] = distance
                            results[algo]['card_id'] = card_id
                    except (TypeError, KeyError):
                        continue
        
        return results
    
    def find_best_feature_match(self, query_descriptors: np.ndarray, feature_type: str):
        """Find best match using feature descriptors (SIFT/AKAZE)."""

        best_match = {'card_id': None, 'matches': -1}
        
        if query_descriptors is None or query_descriptors.size == 0:
            return best_match
        
        if feature_type == 'SIFT' and query_descriptors.dtype != np.float32:
            query_descriptors = query_descriptors.astype(np.float32)
        
        matcher, matcher_name = self.model_manager.get_matcher(feature_type, self.settings.flann_enabled)
        feature_db = self.model_manager.get_feature_database(feature_type)
        
        for card_id, ref_descriptors in feature_db.items():
            if ref_descriptors is None or ref_descriptors.size == 0:
                continue
            
            try:
                matches = matcher.knnMatch(query_descriptors, ref_descriptors, k=2)
                good_matches = []
                
                for match_pair in matches:
                    if len(match_pair) == 2:
                        m, n = match_pair
                        if m.distance < 0.75 * n.distance:
                            good_matches.append(m)
                
                if len(good_matches) > best_match['matches']:
                    best_match['matches'] = len(good_matches)
                    best_match['card_id'] = card_id
                    
            except (cv2.error, ValueError):
                continue
        
        return best_match
    
    def compute_hash_features(self, crop_pil: Image.Image):
        """Compute perceptual hash features for an image crop."""

        upscaled_crop = crop_pil.resize((600, 824), Image.Resampling.BILINEAR)
        
        query_hashes = {}
        if self.settings.algo_enabled.get('phash'):
            query_hashes['phash'] = str(imagehash.phash(upscaled_crop))
        if self.settings.algo_enabled.get('dhash'):
            query_hashes['dhash'] = str(imagehash.dhash(upscaled_crop))
        if self.settings.algo_enabled.get('whash'):
            query_hashes['whash'] = str(imagehash.whash(upscaled_crop))
        
        return query_hashes
    
    def compute_feature_descriptors(self, crop_gray: np.ndarray, feature_type: str):
        """Compute feature descriptors for an image crop."""

        feature_crop_resized = cv2.resize(crop_gray, (300, 418), interpolation=cv2.INTER_AREA)
        feature_crop_enhanced = self.model_manager.clahe.apply(feature_crop_resized)

        if feature_type == 'SIFT':
            detector = self.model_manager.sift
        elif feature_type == 'AKAZE':
            detector = self.model_manager.akaze
        else:
            return None
        
        if detector is None:
            return None
        
        _, descriptors = detector.detectAndCompute(feature_crop_enhanced, None)
        return descriptors
    
    def get_best_identification(self, analysis_data: Dict):
        """Get best identification based on algorithm priority."""

        for algo in self.settings.algo_priority:
            if not self.settings.algo_enabled.get(algo):
                continue
            
            result = None
            winning_algo_name = algo
            
            if 'hash' in algo:
                result = analysis_data.get('hash_results', {}).get(algo)
            else:
                result = analysis_data.get(f'{algo}_result')
                winning_algo_name = f"{algo}_{'flann' if self.settings.flann_enabled else 'bf'}"
            
            if result and result.get('card_id'):
                return winning_algo_name, result
        
        return None, None