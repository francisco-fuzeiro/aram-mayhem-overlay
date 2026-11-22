"""Pinned recognition-only preprocessing ablations for V1.1b research.

Every candidate uses the exact V1.1 ONNX session and CTC dictionary. No
capture/game state or live OCR routing is imported. Preprocessing is the sole
controlled variable; these are exploratory tests on known, correlated crops.
"""
from __future__ import annotations

import statistics
import time

CONFIGS={
    "v4_rgb_pil": ("v4","rgb","pil"),
    "v4_rgb_cv2": ("v4","rgb","cv2"),
    "v4_bgr_pil": ("v4","bgr","pil"),
    "v4_bgr_cv2": ("v4","bgr","cv2"),
    "v5_rgb_pil": ("v5","rgb","pil"),
    "v5_rgb_cv2": ("v5","rgb","cv2"),
    "v5_bgr_pil": ("v5","bgr","pil"),
    "v5_bgr_cv2": ("v5","bgr","cv2"),
}

def prepare_input(img,*,height:int,width:int,color:str,resize:str):
    """RGB/BGR x PIL/OpenCV, same aspect ratio, [-1,1], zero padded tensor."""
    import numpy as np
    from PIL import Image
    if color not in ("rgb","bgr") or resize not in ("pil","cv2"):
        raise ValueError("invalid preprocessing variant")
    if height<1 or width<1:
        raise ValueError("invalid recognizer shape")
    original=np.asarray(img.convert("RGB"))
    if color=="bgr":
        original=original[:,:,::-1].copy()
    scaled_width=max(1,min(width,round(img.width*height/img.height)))
    if resize=="pil":
        resized=np.asarray(Image.fromarray(original).resize(
            (scaled_width,height),Image.Resampling.BILINEAR))
    else:
        import cv2
        resized=cv2.resize(original,(scaled_width,height),interpolation=cv2.INTER_LINEAR)
    tensor=np.zeros((1,3,height,width),dtype=np.float32)
    tensor[0,:,:,:scaled_width]=((resized.astype(np.float32)/255.0-0.5)/0.5).transpose(2,0,1)
    return tensor

class AblationRecognizer:
    """DirectONNX input session/decoder held fixed across controlled variants."""
    def __init__(self,engine,*,color,resize):
        self.engine=engine
        self.color=color
        self.resize=resize

    def rec(self,img):
        from benchmarks.ocr_v11.runner import validate_output_dimensions
        t=time.perf_counter()
        x=prepare_input(img,height=self.engine.height,width=self.engine.width,
                        color=self.color,resize=self.resize)
        prep_ms=1000*(time.perf_counter()-t)
        t=time.perf_counter()
        p=self.engine.session.run(None,{self.engine.input_name:x})[0][0]
        inference_ms=1000*(time.perf_counter()-t)
        if p.ndim!=2:
            raise ValueError("decoder_incompatible")
        validate_output_dimensions(self.engine.version,int(p.shape[-1]),len(self.engine.dictionary))
        best=p.argmax(1)
        conf=p.max(1)
        previous=0
        chars=[]
        confidences=[]
        for idx,confidence in zip(best,conf):
            cur=int(idx)
            if cur!=previous and cur!=0:
                chars.append(self.engine.chars[cur])
                confidences.append(float(confidence))
            previous=cur
        return ("".join(chars).strip(),statistics.mean(confidences) if confidences else 0.0,
                prep_ms,inference_ms)
