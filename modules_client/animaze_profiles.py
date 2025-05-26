# modules_client/animaze_profiles.py

class AnimazeProfiles:
    """Definisi profil ekspresi untuk berbagai kepribadian di Animaze."""
    
    # Mapping kepribadian ke Action Units dan parameter animasi
    PROFILES = {
        "Ceria": {
            "base_expression": {
                "smile": 0.4,           # Senyum dasar
                "eyebrow_raise": 0.2,   # Alis terangkat
                "eye_open": 0.7         # Mata lebih terbuka
            },
            "animation_params": {
                "gesture_frequency": 0.8,  # Frekuensi gerakan tangan
                "head_movement": 0.6,      # Tingkat pergerakan kepala
                "blink_rate": 0.3          # Kecepatan berkedip
            },
            "speech_settings": {
                "mouth_movement": 0.8,     # Rentang gerakan mulut saat bicara
                "gesture_intensity": 0.7,  # Intensitas gerakan tangan saat bicara
                "expression_variance": 0.4  # Variasi ekspresi saat bicara
            }
        },
        "Pemarah": {
            "base_expression": {
                "smile": -0.3,          # Cemberut/marah
                "eyebrow_lower": 0.4,   # Alis menurun
                "eye_squint": 0.3       # Mata menyipit
            },
            "animation_params": {
                "gesture_frequency": 0.5,
                "head_movement": 0.4,
                "blink_rate": 0.2
            },
            "speech_settings": {
                "mouth_movement": 0.6,
                "gesture_intensity": 0.9,  # Gerakan tangan lebih intens
                "expression_variance": 0.2
            }
        },
        "Bijaksana": {
            "base_expression": {
                "smile": 0.1,           # Senyum tipis
                "eyebrow_raise": 0.1,   # Alis sedikit terangkat
                "head_tilt": 0.2        # Kepala sedikit miring
            },
            "animation_params": {
                "gesture_frequency": 0.4,  # Gerakan lebih jarang
                "head_movement": 0.3,      # Gerakan kepala minimal
                "blink_rate": 0.2
            },
            "speech_settings": {
                "mouth_movement": 0.5,
                "gesture_intensity": 0.5,  # Gerakan tangan lebih terukur
                "expression_variance": 0.3
            }
        },
        "Suka Bercanda": {
            "base_expression": {
                "smile": 0.6,           # Senyum lebar
                "eyebrow_raise": 0.3,   # Alis terangkat
                "eye_wide": 0.4         # Mata lebih terbuka
            },
            "animation_params": {
                "gesture_frequency": 0.9,  # Gerakan sangat sering
                "head_movement": 0.8,      # Banyak gerakan kepala
                "blink_rate": 0.4
            },
            "speech_settings": {
                "mouth_movement": 0.9,     # Ekspresi mulut yang lebih
                "gesture_intensity": 0.8,  # Gerakan tangan yang ekspresif
                "expression_variance": 0.7  # Banyak variasi ekspresi
            }
        },
        # Tambahkan profil lainnya sesuai dengan kepribadian di CoHost
    }
    
    @classmethod
    def get_profile(cls, personality):
        """Dapatkan profil berdasarkan kepribadian."""
        return cls.PROFILES.get(personality, cls.PROFILES["Ceria"])  # Default ke Ceria
    
    @classmethod
    def get_action_units(cls, personality, is_speaking=False, speech_intensity=0.5):
        """
        Konversi profil kepribadian ke array Action Units Animaze.
        
        Args:
            personality: Nama kepribadian
            is_speaking: Apakah sedang berbicara
            speech_intensity: Intensitas bicara (0.0-1.0)
            
        Returns:
            numpy array: Action Units untuk Animaze
        """
        import numpy as np
        import random
        import math
        
        # Ambil profil yang sesuai
        profile = cls.get_profile(personality)
        
        # Buat array Action Units
        action_units = np.zeros(60, dtype=np.float32)
        
        # Terapkan ekspresi dasar
        base_expr = profile["base_expression"]
        if "smile" in base_expr:
            action_units[1] = base_expr["smile"]  # AU untuk senyum
        if "eyebrow_raise" in base_expr:
            action_units[2] = base_expr["eyebrow_raise"]  # AU untuk alis naik
        if "eyebrow_lower" in base_expr:
            action_units[4] = base_expr["eyebrow_lower"]  # AU untuk alis turun
        if "eye_squint" in base_expr:
            action_units[6] = base_expr["eye_squint"]  # AU untuk mata menyipit
        if "eye_wide" in base_expr:
            action_units[5] = base_expr["eye_wide"]  # AU untuk mata terbuka lebar
        
        # Tambahan untuk pergerakan saat bicara
        if is_speaking:
            speech = profile["speech_settings"]
            
            # Pergerakan mulut saat bicara
            mouth_open = speech["mouth_movement"] * speech_intensity
            # Variasi alami dengan fungsi sinus
            variance = 0.2 * math.sin(time.time() * 8)
            action_units[25] = max(0, min(1, mouth_open + variance))  # AU untuk mulut terbuka
            
            # Gerakan tangan berdasarkan intensitas dan frekuensi
            anim_params = profile["animation_params"]
            if random.random() < anim_params["gesture_frequency"] * 0.1:  # Kontrol frekuensi gerakan
                gesture_type = random.randint(0, 3)
                gesture_strength = speech["gesture_intensity"] * speech_intensity
                
                if gesture_type == 0:
                    action_units[50] = gesture_strength  # Tangan kanan ke atas
                elif gesture_type == 1:
                    action_units[51] = gesture_strength  # Tangan kiri ke atas
                elif gesture_type == 2:
                    action_units[52] = gesture_strength * 0.8  # Kedua tangan
                elif gesture_type == 3:
                    action_units[53] = gesture_strength * 0.7  # Gerakan tangan lainnya
        
        return action_units