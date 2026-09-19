import warnings

from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import MultiLabelBinarizer

from src.utils.logger import get_logger

logger = get_logger("preprocessing")


class EquipmentEncoder(BaseEstimator, TransformerMixin):
    def __init__(self, min_frequency=0.05):
        self.min_frequency = min_frequency
        self.mlb = None
        self.features_ = None

    def fit(self, X, y=None):
        logger.info("EquipmentEncoder.fit — min_frequency=%.3f", self.min_frequency)
        # 1. Grab the single equipment column
        col_name = X.columns[0]

        # 2. Count frequencies of all equipment
        temp_mlb = MultiLabelBinarizer()
        matrix = temp_mlb.fit_transform(X[col_name])
        frequencies = matrix.mean(axis=0)

        # 3. Keep only equipment that appears in > min_frequency of cars
        mask = frequencies >= self.min_frequency
        self.features_ = temp_mlb.classes_[mask]
        logger.debug(
            "EquipmentEncoder.fit — kept %d/%d equipment features",
            mask.sum(),
            len(mask),
        )

        # 4. Lock a permanent MLB to ONLY those frequent features
        self.mlb = MultiLabelBinarizer(classes=self.features_)
        self.mlb.fit(X[col_name])
        logger.info("EquipmentEncoder.fit complete")
        return self

    def transform(self, X):
        col_name = X.columns[0]
        logger.debug("EquipmentEncoder.transform — rows=%d", len(X))
        # Any rare or unseen equipment is safely ignored!
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = self.mlb.transform(X[col_name])
        logger.debug("EquipmentEncoder.transform — output shape=%s", result.shape)
        return result

    def get_feature_names_out(self, input_features=None):
        # This allows preprocessor.get_feature_names_out() to work nicely
        return [f"equip_{f}" for f in self.features_]
