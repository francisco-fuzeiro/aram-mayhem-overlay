"""Pure preprocessing contract tests; real inference is a separate CI step."""
import numpy as np
import pytest
from PIL import Image
from benchmarks.ocr_v11b.controlled import CONFIGS,prepare_input

def test_variants_are_only_pinned_v4_v5_and_color_resize_changes():
    assert len(CONFIGS)==8
    assert set(version for version,_,_ in CONFIGS.values())=={"v4","v5"}
    assert all(c in ("rgb","bgr") and r in ("pil","cv2")
               for _,c,r in CONFIGS.values())

def test_rgb_bgr_have_identical_geometry_but_different_channels():
    source=Image.fromarray(np.array([[[255,0,0],[0,255,0]]],dtype=np.uint8),"RGB")
    rgb=prepare_input(source,height=2,width=8,color="rgb",resize="pil")
    bgr=prepare_input(source,height=2,width=8,color="bgr",resize="pil")
    assert rgb.shape==(1,3,2,8) and bgr.shape==rgb.shape
    assert rgb.dtype==np.float32
    assert rgb[0,0,0,0]>0.99 and rgb[0,2,0,0]<-0.99
    assert bgr[0,0,0,0]<-0.99 and bgr[0,2,0,0]>0.99
    assert np.all(rgb[0,:,:,4:]==0)  # normalized zero padding
    assert np.all(bgr[0,:,:,4:]==0)

def test_cv2_interpolation_is_a_controlled_variant_not_label_or_decoder():
    img=Image.fromarray(np.full((4,8,3),128,dtype=np.uint8),"RGB")
    pil=prepare_input(img,height=8,width=32,color="rgb",resize="pil")
    cv=prepare_input(img,height=8,width=32,color="rgb",resize="cv2")
    assert pil.shape==cv.shape==(1,3,8,32)
    assert np.max(np.abs(pil-cv))<.02

@pytest.mark.parametrize("color,resize",[("auto","pil"),("rgb","nearest"),
                                         ("bgr","none")])
def test_unapproved_preprocessing_configuration_rejected(color,resize):
    img=Image.new("RGB",(3,3))
    with pytest.raises(ValueError,match="variant"):
        prepare_input(img,height=48,width=320,color=color,resize=resize)
