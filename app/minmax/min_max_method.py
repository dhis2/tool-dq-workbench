from enum import Enum

class MinMaxMethod(Enum):
    PREV_MAX = "PREV_MAX"
    ZSCORE = "ZSCORE"
    MAD = "MAD"
    BOXCOX = "BOXCOX"
    IQR = "IQR"

    @classmethod
    def values(cls):
        return [m.value for m in cls]

    @classmethod
    def label_map(cls):
        return {
            "PREV_MAX": "Previous Max",
            "ZSCORE": "Z-Score",
            "MAD": "MAD (Median Absolute Deviation)",
            "BOXCOX": "Box-Cox",
            "IQR": "Interquartile Range (IQR)"
        }
