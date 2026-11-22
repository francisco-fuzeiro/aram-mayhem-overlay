"""Pinned recognition-only preprocessing ablations for V1.1b research.

Every candidate uses the exact V1.1 ONNX session and CTC dictionary. No
capture/game state or live OCR routing is imported. Preprocessing is the sole
controlled variable; these are exploratory tests on known, correlated crops.
"""
from __future__ import annotations

import statistics
import time

CONFIGS={
    "v4_rgb_pil": ("v4","rgb","pil","round",False),
    "v4_rgb_cv2": ("v4","rgb","cv2","round",False),
    "v4_bgr_pil": ("v4","bgr","pil","round",False),
    "v4_bgr_cv2": ("v4","bgr","cv2","round",False),
    "v4_bgr_cv2_ceil": ("v4","bgr","cv2","ceil",False),
    "v4_bgr_cv2_ceil_dynamic": ("v4","bgr","cv2","ceil",True),
    "v5_rgb_pil": ("v5","rgb","pil","round",False),
    "v5_rgb_cv2": ("v5","rgb","cv2","round",False),
    "v5_bgr_pil": ("v5","bgr","pil","round",False),
    "v5_bgr_cv2": ("v5","bgr","cv2","round",False),
    "v5_bgr_cv2_ceil": ("v5","bgr","cv2","ceil",False),
}

def prepare_input(img,*,height:int,width:int,color:str,resize:str,rounding:str="round"):
    """RGB/BGR x PIL/OpenCV, same aspect ratio, [-1,1], zero padded tensor."""
    import numpy as np
    from PIL import Image
    if color not in ("rgb","bgr") or resize not in ("pil","cv2") or rounding not in ("round","ceil"):
        raise ValueError("invalid preprocessing variant")
    if height<1 or width<1:
        raise ValueError("invalid recognizer shape")
    original=np.asarray(img.convert("RGB"))
    if color=="bgr":
        original=original[:,:,::-1].copy()
    import math
    target=img.width*height/img.height
    scaled_width=max(1,min(width,math.ceil(target) if rounding=="ceil" else round(target)))
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
    def __init__(self,engine,*,color,resize,rounding="round",dynamic_width=False):
        self.engine=engine
        self.color=color
        self.resize=resize
        self.rounding=rounding
        self.dynamic_width=dynamic_width

    def rec(self,img):
        from benchmarks.ocr_v11.runner import validate_output_dimensions
        t=time.perf_counter()
        import math
        width=(max(self.engine.width,math.ceil(img.width*self.engine.height/img.height))
               if self.dynamic_width else self.engine.width)
        model_width=self.engine.session.get_inputs()[0].shape[3]
        if isinstance(model_width,int) and width!=model_width:
            raise ValueError("pinned ONNX input forbids dynamic width")
        x=prepare_input(img,height=self.engine.height,width=width,
                        color=self.color,resize=self.resize,rounding=self.rounding)
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
