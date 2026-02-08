#!/usr/bin/env python3
import sys, importlib, torch, cv2, pytesseract, re, os

YOLO_DIR = '/home/pi/yolov7'
WEIGHTS  = os.path.join(YOLO_DIR, 'lp-tiny.pt')
IMAGE    = '/home/pi/Partage/photo/photo_20250715_101706.jpg'  # ← ta photo

# --- rendez le dépôt importable ---
sys.path.insert(0, YOLO_DIR)
yolo_mod = importlib.import_module('models.yolo')
torch.serialization.add_safe_globals([yolo_mod.Model])   # <- correct !

# --- charge le modèle (CPU, offline) ---
model = torch.hub.load(YOLO_DIR, 'custom', WEIGHTS, source='local').eval()

# --- détection -> crop -> OCR ---
img = cv2.imread(IMAGE)
assert img is not None, f"Image introuvable : {IMAGE}"

for *box, _, _ in model(img, size=640).xyxy[0]:
    x1, y1, x2, y2 = map(int, box)
    crop = img[y1:y2, x1:x2]
    cv2.imwrite('debug_crop.jpg', crop)
    txt = pytesseract.image_to_string(crop, lang='eng+fra')
    plate = re.findall(r'[A-Z0-9]{2}-?\d{3}-?[A-Z0-9]{2}',
                       txt.replace(' ', '').replace('_', '-'))
    print("OCR brut :", txt.strip())
    print("Plaque   :", plate or "non trouvée")
    break
